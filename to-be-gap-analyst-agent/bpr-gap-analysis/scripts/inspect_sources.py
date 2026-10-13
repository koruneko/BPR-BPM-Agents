"""Build an exact source index and check a gap delivery; no network or source edits."""
import argparse, csv, json, re, sys
from pathlib import Path

QUESTION_KEYS={'open_questions','unresolved_questions','analysis_open_questions'}
def pack_files(text):
    blocks=re.findall(r'^## FILE: (.+?)\r?\n(?:SHA256: .*?\r?\n)?BEGIN FILE\r?\n(.*?)^END FILE\s*$',text,re.M|re.S)
    if not blocks: raise ValueError('Supported pack requires ## FILE:, BEGIN FILE, END FILE markers; do not guess or summarize missing content.')
    result={}
    for name, body in blocks:
        if name in result:
            raise ValueError('Duplicate ## FILE name in source pack: '+name)
        result[name]=body
    return result

def scalar(s):
    if s in ('|','>') or s.startswith(('|-','>-','|+','>+')): raise ValueError('Block scalar requires a YAML parser')
    if s.startswith('"'): return json.loads(s)
    if s.startswith("'") and s.endswith("'"): return s[1:-1].replace("''", "'")
    return s

def question_rows(file,text):
    try:
        import yaml
    except ImportError:
        yaml=None
    out=[]
    if yaml:
        def walk(obj,path=''):
            if isinstance(obj,dict):
                for key,value in obj.items():
                    p=path+'.'+key if path else key
                    if key in QUESTION_KEYS and isinstance(value,list):
                        for i,v in enumerate(value):
                            if isinstance(v,str): out.append({'file':file,'field_path':f'{p}[{i}]','original_text':v})
                            else: raise ValueError('Question is not a scalar string: '+p)
                    walk(value,p)
            elif isinstance(obj,list):
                for i,v in enumerate(obj): walk(v,f'{path}[{i}]')
        walk(yaml.safe_load(text))
    else:
        # Explicit supported subset for the BPM/BPR scalar question arrays.
        # Unsupported placement fails instead of inventing paths.
        lines=text.splitlines(); imp=-1; root=None
        for n,line in enumerate(lines):
            m=re.match(r'^([A-Za-z_]+):',line)
            if m: root=m[1]
            if re.match(r'^- id: IMP-',line): imp+=1
            key=None
            if line=='  open_questions:' and root=='metadata': key='metadata.open_questions'
            elif line=='  unresolved_questions:' and root=='improvements': key=f'improvements[{imp}].unresolved_questions'
            elif line=='analysis_open_questions:': key='analysis_open_questions'
            elif re.match(r'^\s*(open_questions|unresolved_questions|analysis_open_questions):',line):
                if line.strip().endswith('[]'): continue
                raise ValueError('Question placement needs YAML parser: '+line)
            if key:
                indent=len(line)-len(line.lstrip()); index=0
                for child in lines[n+1:]:
                    if not child.startswith(' '*indent+'- '): break
                    out.append({'file':file,'field_path':f'{key}[{index}]','original_text':scalar(child[indent+2:])}); index+=1
    return out

def ids(text,section):
    m=re.search(r'^'+section+r':\s*\n(.*?)(?=^[A-Za-z_]+:|\Z)',text,re.M|re.S)
    return re.findall(r'^- id: (.+)$',m[1],re.M) if m else []


def _load_yaml_dict(text):
    try:
        import yaml
    except ImportError:
        return None
    try:
        obj=yaml.safe_load(text)
    except Exception as exc:
        raise ValueError('Invalid YAML in decision or To-Be source: '+str(exc)) from exc
    if not isinstance(obj,dict):
        raise ValueError('Expected a YAML mapping for decision or To-Be source')
    return obj


def _fallback_decisions(text):
    # Supported standard BPR export subset only. Fail closed on any other layout.
    section=re.search(r'^decisions:\s*\n(.*?)(?=^[A-Za-z_][\w-]*:|\Z)',text,re.M|re.S)
    if not section:
        raise ValueError('decisions require YAML parser or standard BPR export format')
    rows=[]; current=None
    for line in section.group(1).splitlines():
        m=re.fullmatch(r'- improvement_id:\s*(IMP-[\w-]+)\s*',line)
        if m:
            if current is not None: rows.append(current)
            current={'improvement_id':m.group(1)}
            continue
        m=re.fullmatch(r'  (decision|condition|note):\s*(.*?)\s*',line)
        if m and current is not None:
            current[m.group(1)]=None if m.group(2) in {'null','~',''} else scalar(m.group(2))
            continue
        if line.strip() and not line.startswith('  ') and not line.startswith('#'):
            raise ValueError('Unsupported decisions YAML structure without PyYAML: '+line)
    if current: rows.append(current)
    return {'decisions': rows}


def _fallback_to_be(text):
    # Indentation-sensitive subset matching BPR's generated process.bpr YAML.
    process=re.search(r'^(?:process|metadata):\s*\n(.*?)(?=^[A-Za-z_][\w-]*:|\Z)',text,re.M|re.S)
    if not process:
        raise ValueError('To-Be requires a process section')
    bpr=re.search(r'^  bpr:\s*\n(.*?)(?=^  [A-Za-z_][\w-]*:|\Z)',process.group(1),re.M|re.S)
    if not bpr:
        raise ValueError('To-Be requires process.bpr section')
    content=bpr.group(1)
    result={}; current_key=None; current_row=None
    for line in content.splitlines():
        key=re.fullmatch(r'    (applied_improvements|conditional_improvements|change_log):\s*(\[\])?\s*',line)
        if key:
            current_key=key.group(1)
            result[current_key]=[]
            current_row=None
            continue
        if current_key in ('applied_improvements','conditional_improvements'):
            match=re.fullmatch(r'    - (IMP-[\w-]+)\s*',line)
            if match:
                result[current_key].append(match.group(1))
                continue
            if current_key=='conditional_improvements':
                match=re.fullmatch(r'    - improvement_id:\s*(IMP-[\w-]+)\s*',line)
                if match:
                    current_row={'improvement_id':match.group(1)}
                    result[current_key].append(current_row)
                    continue
                match=re.fullmatch(r'      condition:\s*(.*?)\s*',line)
                if match and current_row is not None:
                    current_row['condition']=None if match.group(1) in {'null','~',''} else scalar(match.group(1))
                    continue
        if current_key=='change_log':
            match=re.fullmatch(r'    - improvement_id:\s*(IMP-[\w-]+)\s*',line)
            if match:
                current_row={'improvement_id':match.group(1)}
                result[current_key].append(current_row)
                continue
            match=re.fullmatch(r'      (action|condition):\s*(.*?)\s*',line)
            if match and current_row is not None:
                current_row[match.group(1)]=None if match.group(2) in {'null','~',''} else scalar(match.group(2))
                continue
        # Unknown fields may occur inside change_log entries: they are evidence,
        # not adoption controls. Only direct declaration and action/condition are read.
    if not all(k in result for k in ('applied_improvements','conditional_improvements','change_log')):
        raise ValueError('Incomplete To-Be process.bpr adoption metadata without PyYAML')
    return {'process':{'bpr':result}}


def parse_decisions(text):
    obj=_load_yaml_dict(text)
    if obj is None: obj=_fallback_decisions(text)
    rows=obj.get('decisions')
    if not isinstance(rows,list) or not rows:
        raise ValueError('improvement-decisions.yaml must contain non-empty decisions list')
    result={}
    for row in rows:
        if not isinstance(row,dict) or not isinstance(row.get('improvement_id'),str) or not isinstance(row.get('decision'),str):
            raise ValueError('Malformed improvement decision row')
        imp=row['improvement_id']
        if imp in result:
            raise ValueError('Duplicate improvement decision: '+imp)
        result[imp]={'decision':row['decision'].lower().strip(), 'condition':row.get('condition'), 'note':row.get('note')}
    return result


def parse_to_be_scope(text):
    obj=_load_yaml_dict(text)
    if obj is None: obj=_fallback_to_be(text)
    process=obj.get('process') or {}
    bpr=process.get('bpr') if isinstance(process,dict) else None
    if not isinstance(bpr,dict):
        metadata=obj.get('metadata')
        bpr=metadata.get('bpr') if isinstance(metadata,dict) else None
    if not isinstance(bpr,dict):
        raise ValueError('To-Be process lacks process.bpr or metadata.bpr adoption metadata')
    applied=bpr.get('applied_improvements')
    conditional=bpr.get('conditional_improvements')
    if not isinstance(applied,list) or not isinstance(conditional,list):
        raise ValueError('To-Be process lacks applied_improvements or conditional_improvements arrays')
    if not all(isinstance(x,str) for x in applied):
        raise ValueError('To-Be applied improvements must be string IDs')
    conditional_rows={}
    for row in conditional:
        if isinstance(row,str):
            imp=row; condition=None
        elif isinstance(row,dict) and isinstance(row.get('improvement_id'),str):
            imp=row['improvement_id']; condition=row.get('condition')
        else:
            raise ValueError('Malformed To-Be conditional improvement')
        if imp in conditional_rows:
            raise ValueError('Duplicate To-Be conditional improvement: '+imp)
        conditional_rows[imp]=condition
    if len(applied)!=len(set(applied)):
        raise ValueError('Duplicate improvements in To-Be applied list')
    if set(conditional_rows) - set(applied):
        raise ValueError('To-Be conditional improvements must also be in applied_improvements')
    change_log=bpr.get('change_log')
    if not isinstance(change_log,list):
        raise ValueError('To-Be process lacks process.bpr.change_log')
    actions={}
    for row in change_log:
        if not isinstance(row,dict) or not isinstance(row.get('improvement_id'),str):
            raise ValueError('Malformed To-Be change_log row')
        imp=row['improvement_id']
        if imp in actions:
            raise ValueError('Duplicate To-Be change_log: '+imp)
        actions[imp]={'action':row.get('action'),'condition':row.get('condition')}
    return {'applied':applied,'conditional':conditional_rows,'change_log':actions}

def inspect(files):
    index={'source_question_lineage':[], 'entity_sets':{}, 'improvement_sets':{}, 'decision_sets':{}, 'to_be_applied_sets':{}, 'unsupported':[]}
    for file,text in files.items():
        if not file.endswith(('.yaml','.yml')): continue
        try: index['source_question_lineage']+=question_rows(file,text)
        except Exception as e: index['unsupported'].append({'file':file,'reason':str(e)})
        entity={s:ids(text,s) for s in ('participants','nodes','edges')}
        if entity['nodes']: index['entity_sets'][file]=entity
        improvement_ids=ids(text,'improvements')
        if improvement_ids: index['improvement_sets'][file]=improvement_ids
        if file.endswith(('improvement-decisions.yaml','improvement-decisions.yml')):
            try:
                index['decision_sets'][file]=parse_decisions(text)
            except ValueError as exc:
                index['unsupported'].append({'file':file,'reason':str(exc)})
        if file.endswith(('to-be-process.yaml','to-be-process.yml')):
            try:
                index['to_be_applied_sets'][file]=parse_to_be_scope(text)
            except ValueError as exc:
                index['unsupported'].append({'file':file,'reason':str(exc)})
    return index

def validate(index,data):
    issues=[]
    expected={(x['file'],x['field_path']):x['original_text'] for x in index['source_question_lineage']}
    rows=data.get('coverage',{}).get('source_question_lineage',[])
    actual={}
    for r in rows:
        key=(r.get('file'),r.get('field_path'))
        if key in actual: issues.append('Duplicate source occurrence: '+str(key))
        actual[key]=r.get('original_text')
        if key not in expected or expected[key]!=r.get('original_text'): issues.append('Wrong path or original text: '+str(key))
        if r.get('question_id') not in {q['id'] for q in data.get('questions',[])}: issues.append('Unknown question ID: '+str(key))
    for key in expected.keys()-actual.keys(): issues.append('Missing source occurrence: '+str(key))
    for role,side in [('as_is_process','as_is_ids'),('to_be_process','to_be_ids')]:
        source=next((x['file'] for x in data.get('source_manifest',[]) if x.get('artifact_role')==role),None)
        if source not in index['entity_sets']:
            issues.append('Missing source_manifest process role: '+role); continue
        for section,types in [('participants',{'participant'}),('nodes',{'node'}),('edges',{'edge','flow','sequence_flow'})]:
            expected_list=list(index['entity_sets'][source][section])
            expected_ids=set(expected_list)
            actual_list=[i for m in data.get('mappings',[]) if m.get('type') in types for i in m.get(side,[])]
            actual_ids=set(actual_list)
            if expected_ids!=actual_ids: issues.append(f'{role} {section} ID mismatch missing={sorted(expected_ids-actual_ids)} unknown={sorted(actual_ids-expected_ids)}')
            duplicate_ids=sorted({i for i in actual_list if actual_list.count(i)>1})
            if duplicate_ids: issues.append(f'{role} {section} IDs mapped more than once: {duplicate_ids}')
    as_source=next((x['file'] for x in data.get('source_manifest',[]) if x.get('artifact_role')=='as_is_process'),None)
    to_source=next((x['file'] for x in data.get('source_manifest',[]) if x.get('artifact_role')=='to_be_process'),None)
    if as_source in index['entity_sets'] and to_source in index['entity_sets']:
        for section,types in [('participants',{'participant'}),('nodes',{'node'}),('edges',{'edge','flow','sequence_flow'})]:
            common=set(index['entity_sets'][as_source][section]) & set(index['entity_sets'][to_source][section])
            for entity_id in common:
                if not any(m.get('type') in types and entity_id in (m.get('as_is_ids') or []) and entity_id in (m.get('to_be_ids') or []) for m in data.get('mappings',[])):
                    issues.append(f'Common {section} ID must be compared in one semantic mapping: {entity_id}')
    improvement_source=next((x['file'] for x in data.get('source_manifest',[]) if x.get('artifact_role')=='improvement_analysis'),None)
    expected_imp=set(index.get('improvement_sets',{}).get(improvement_source,[]))
    lineage=data.get('coverage',{}).get('improvement_lineage',[])
    actual_imp=[r.get('improvement_id') for r in lineage if r.get('improvement_id')]
    if expected_imp:
        if set(actual_imp)!=expected_imp: issues.append(f'improvement ID mismatch missing={sorted(expected_imp-set(actual_imp))} unknown={sorted(set(actual_imp)-expected_imp)}')
        dup=sorted({i for i in actual_imp if actual_imp.count(i)>1})
        if dup: issues.append('Improvement IDs recorded more than once: '+str(dup))
        for r in lineage:
            if r.get('improvement_id') in expected_imp:
                if r.get('status') in (None,'','unmapped','未整理'): issues.append('Improvement not classified: '+str(r.get('improvement_id')))
                if not (r.get('gap_ids') or r.get('action_ids') or r.get('no_gap_reason')): issues.append('Improvement lacks GAP/ACT or no_gap_reason: '+str(r.get('improvement_id')))
    # A decision-approved IMP must be present in the adopted To-Be scope; a
    # rejected/pending IMP must not be presented as applied. Verify the authoritative
    # decision records, actual To-Be application metadata, and analysis lineage.
    decisions_file=next((x['file'] for x in data.get('source_manifest',[]) if x.get('artifact_role')=='improvement_decisions'),None)
    decisions=index.get('decision_sets',{}).get(decisions_file)
    adopted=index.get('to_be_applied_sets',{}).get(to_source)
    if decisions is None:
        issues.append('Missing or unparseable improvement-decisions.yaml role')
    if adopted is None:
        issues.append('Missing or unparseable To-Be applied improvement metadata')
    if decisions is not None and adopted is not None:
        if set(decisions)!=expected_imp:
            issues.append('Decision records do not match improvement-analysis IMP set')
        applied=set(adopted['applied'])
        conditional=set(adopted['conditional'])
        allowed_applied={'approved'}
        allowed_conditional={'conditional_approved','approved_with_conditions','conditional','conditionally_approved'}
        for imp, record in decisions.items():
            d=record['decision']
            if d in allowed_applied:
                if imp not in applied or imp in conditional:
                    issues.append(f'{imp} approved decision not matched by To-Be applied scope')
            elif d in allowed_conditional:
                if imp not in applied or imp not in conditional:
                    issues.append(f'{imp} conditional decision not matched by To-Be conditional scope')
                if not (record.get('condition') or record.get('note')):
                    issues.append(f'{imp} conditional decision requires documented note/condition')
                if not adopted['conditional'].get(imp):
                    issues.append(f'{imp} To-Be conditional improvement requires documented condition')
            elif d in {'rejected','not_approved','deferred','pending','hold','on_hold','excluded'}:
                if imp in applied or imp in conditional:
                    issues.append(f'{imp} non-approved decision was applied in To-Be')
            else:
                issues.append(f'{imp} unknown improvement decision: {d!r}')
        if (applied | conditional) - set(decisions):
            issues.append('To-Be applies an IMP without a decision record')
        if set(adopted['change_log']) != applied:
            issues.append('To-Be change_log does not exactly match applied IMP IDs')
        for imp in applied:
            action=adopted['change_log'].get(imp,{}).get('action')
            if not isinstance(action,str) or not action.strip():
                issues.append(f'{imp} To-Be change_log lacks a recorded change action')
        for row in lineage:
            imp=row.get('improvement_id')
            if imp not in decisions: continue
            status=str(row.get('status','')).lower()
            expected_applied=imp in applied|conditional
            if expected_applied and status in {'rejected','excluded','deferred','not_approved','not_applied'}:
                issues.append(f'{imp} analysis lineage incorrectly excludes an applied decision')
            if not expected_applied and (status in {'applied','approved','implemented','conditional','conditionally_approved'} or (row.get('gap_ids') or row.get('action_ids'))):
                issues.append(f'{imp} analysis lineage treats a non-applied decision as an applied Gap/ACT')
    return {'status':'pass' if not issues and not index['unsupported'] else 'fail','issues':issues,'unsupported':index['unsupported'],'source_question_occurrences':len(expected),'improvement_count':len(expected_imp)}

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--pack',required=True); p.add_argument('--analysis'); p.add_argument('--output',required=True); a=p.parse_args()
    index=inspect(pack_files(Path(a.pack).read_text(encoding='utf-8-sig')))
    if a.analysis: index['validation']=validate(index,json.loads(Path(a.analysis).read_text(encoding='utf-8-sig')))
    Path(a.output).write_text(json.dumps(index,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'source_question_occurrences':len(index['source_question_lineage']),'validation':index.get('validation'),'unsupported':index['unsupported']},ensure_ascii=False))
    sys.exit(bool(index['unsupported']) or (a.analysis and index['validation']['status']!='pass'))
