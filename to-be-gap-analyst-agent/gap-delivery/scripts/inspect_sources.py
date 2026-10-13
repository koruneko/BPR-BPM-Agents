"""Build an exact source index and check a gap delivery; no network or source edits."""
import argparse, csv, json, re, sys
from pathlib import Path

QUESTION_KEYS={'open_questions','unresolved_questions','analysis_open_questions'}
def pack_files(text):
    blocks=re.findall(r'^## FILE: (.+?)\r?\n(?:SHA256: .*?\r?\n)?BEGIN FILE\r?\n(.*?)^END FILE\s*$',text,re.M|re.S)
    if not blocks: raise ValueError('Supported pack requires ## FILE:, BEGIN FILE, END FILE markers; do not guess or summarize missing content.')
    return dict(blocks)

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

def inspect(files):
    index={'source_question_lineage':[], 'entity_sets':{}, 'improvement_sets':{}, 'unsupported':[]}
    for file,text in files.items():
        if not file.endswith(('.yaml','.yml')): continue
        try: index['source_question_lineage']+=question_rows(file,text)
        except Exception as e: index['unsupported'].append({'file':file,'reason':str(e)})
        entity={s:ids(text,s) for s in ('participants','nodes','edges')}
        if entity['nodes']: index['entity_sets'][file]=entity
        improvement_ids=ids(text,'improvements')
        if improvement_ids: index['improvement_sets'][file]=improvement_ids
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
    return {'status':'pass' if not issues and not index['unsupported'] else 'fail','issues':issues,'unsupported':index['unsupported'],'source_question_occurrences':len(expected),'improvement_count':len(expected_imp)}

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('--pack',required=True); p.add_argument('--analysis'); p.add_argument('--output',required=True); a=p.parse_args()
    index=inspect(pack_files(Path(a.pack).read_text(encoding='utf-8-sig')))
    if a.analysis: index['validation']=validate(index,json.loads(Path(a.analysis).read_text(encoding='utf-8-sig')))
    Path(a.output).write_text(json.dumps(index,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'source_question_occurrences':len(index['source_question_lineage']),'validation':index.get('validation'),'unsupported':index['unsupported']},ensure_ascii=False))
    sys.exit(bool(index['unsupported']) or (a.analysis and index['validation']['status']!='pass'))
