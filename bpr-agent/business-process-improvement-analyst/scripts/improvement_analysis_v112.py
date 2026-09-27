#!/usr/bin/env python3
import argparse, hashlib, json, re, sys
import yaml

REC = {"eliminate","simplify","consolidate","standardize","relocate","automate","assist","retain"}
LEVELS = {"full","partial","assist"}
QUAL = {"high","medium","low"}
SCOPES = {"task","process"}
DEP_TYPES = {"requires","any_of","enhances"}
FIT = {"primary","complementary","alternative"}
PROCESS_PATTERNS = {"loop","handoff","duplicate_entry","parallel_dependency"}


def load_yaml(path):
    with open(path, encoding='utf-8') as f:
        return yaml.safe_load(f)

def dump_yaml(data, path):
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        yaml.safe_dump(data, f, allow_unicode=True, sort_keys=False, width=120)

def read_json(args):
    if args.json:
        return json.loads(args.json)
    text = sys.stdin.read()
    if not text.strip():
        raise ValueError('JSON input is empty')
    return json.loads(text)

def is_str_list(v):
    return isinstance(v, list) and all(isinstance(x, str) and x.strip() for x in v)

def validate(data, process):
    errors=[]; warnings=[]
    if not isinstance(data, dict):
        return ['analysis must be an object'], warnings
    if str(data.get('analysis_version')) != '1.5': errors.append('analysis_version must be 1.5')
    aid=data.get('analysis_id')
    if not isinstance(aid,str) or not re.fullmatch(r'bpr-a-[0-9a-f]{16}', aid): errors.append('analysis_id must match bpr-a-<16 hex>')
    sp=data.get('source_process') or {}
    p=(process or {}).get('process') or {}
    if sp.get('id') != p.get('id'): errors.append('source_process.id must match As-Is process.id')
    if str(sp.get('version')) != str(p.get('version')): errors.append('source_process.version must match As-Is process.version')
    tasks={n.get('id') for n in (process.get('nodes') or []) if isinstance(n,dict) and n.get('type')=='task'}

    sources=data.get('research_sources') or []
    src_ids=set()
    if not isinstance(sources,list): errors.append('research_sources must be a list'); sources=[]
    for s in sources:
        if not isinstance(s,dict): errors.append('research_sources entries must be objects'); continue
        sid=s.get('id')
        if not isinstance(sid,str) or not re.fullmatch(r'SRC-\d{3,}', sid): errors.append(f'invalid research source id: {sid}')
        elif sid in src_ids: errors.append(f'duplicate research source id: {sid}')
        else: src_ids.add(sid)
        if not isinstance(s.get('title'),str) or not s.get('title','').strip(): warnings.append(f'{sid or "source"}: title is empty')
        if s.get('url') is not None and (not isinstance(s.get('url'),str) or not s.get('url','').startswith(('http://','https://'))): errors.append(f'{sid}: url must be http(s)')

    imps=data.get('improvements') or []
    if not isinstance(imps,list): errors.append('improvements must be a list'); imps=[]
    ids=[]; id_set=set()
    for i,imp in enumerate(imps,1):
        if not isinstance(imp,dict): errors.append(f'improvement #{i} must be an object'); continue
        iid=imp.get('id')
        if not isinstance(iid,str) or not re.fullmatch(r'IMP-\d{3,}', iid): errors.append(f'invalid improvement id: {iid}')
        elif iid in id_set: errors.append(f'duplicate improvement id: {iid}')
        else: ids.append(iid); id_set.add(iid)

    for i,imp in enumerate(imps,1):
        if not isinstance(imp,dict): continue
        iid=imp.get('id') or f'#{i}'
        if not isinstance(imp.get('title'),str) or not imp.get('title','').strip(): errors.append(f'{iid}: title is required')
        scope=imp.get('scope')
        if scope not in SCOPES: errors.append(f'{iid}: scope must be task or process')
        targets=imp.get('target_tasks') or []
        if not isinstance(targets,list) or not all(isinstance(x,str) for x in targets): errors.append(f'{iid}: target_tasks must be a string list'); targets=[]
        unknown=[x for x in targets if x not in tasks]
        if unknown: errors.append(f'{iid}: unknown target task ids: {unknown}')
        if scope=='task' and not targets: errors.append(f'{iid}: task-scope improvement requires target_tasks')
        recs=imp.get('recommendations') or []
        if not isinstance(recs,list) or not recs: errors.append(f'{iid}: recommendations must be a non-empty list'); recs=[]
        bad=[r for r in recs if r not in REC]
        if bad: errors.append(f'{iid}: invalid recommendations: {bad}')
        if len(recs)!=len(set(recs)): warnings.append(f'{iid}: duplicate recommendation values')
        if 'retain' in recs and 'eliminate' in recs: errors.append(f'{iid}: retain and eliminate cannot be combined')
        for field in ('rationale','proposed_change'):
            if not isinstance(imp.get(field),str) or not imp.get(field,'').strip(): errors.append(f'{iid}: {field} is required')
        eff=imp.get('expected_effect') or {}
        if eff.get('impact') not in QUAL: errors.append(f'{iid}: expected_effect.impact must be high/medium/low')
        pr=imp.get('priority') or {}
        for k in ('effort','risk','confidence'):
            if pr.get(k) not in QUAL: errors.append(f'{iid}: priority.{k} must be high/medium/low')
        auto=imp.get('automation')
        if auto is not None:
            if not isinstance(auto,dict): errors.append(f'{iid}: automation must be an object')
            else:
                cand=auto.get('candidate')
                if cand is not None and not isinstance(cand,bool): errors.append(f'{iid}: automation.candidate must be true/false/null')
                lvl=auto.get('level')
                if lvl is not None and lvl not in LEVELS: errors.append(f'{iid}: automation.level invalid')
                if cand is False and lvl is not None: errors.append(f'{iid}: automation.level must be empty when candidate=false')
                if cand is None and lvl is not None: errors.append(f'{iid}: automation.level requires candidate=true')
                if 'assist' in recs and 'automate' not in recs and not (cand is True and lvl=='assist'): warnings.append(f'{iid}: assist-only recommendation normally uses candidate=true and level=assist')
                if 'automate' in recs and not (cand is True and lvl in {'full','partial'}): warnings.append(f'{iid}: automate recommendation normally uses candidate=true and level=full/partial')

        deps=imp.get('dependencies') or []
        if not isinstance(deps,list): errors.append(f'{iid}: dependencies must be a list'); deps=[]
        for d in deps:
            if not isinstance(d,dict): errors.append(f'{iid}: dependency entries must be objects'); continue
            typ=d.get('type')
            if typ not in DEP_TYPES: errors.append(f'{iid}: dependency.type must be requires/any_of/enhances')
            dep_ids=d.get('improvement_ids') or []
            if not is_str_list(dep_ids): errors.append(f'{iid}: dependency.improvement_ids must be a non-empty string list'); dep_ids=[]
            if iid in dep_ids: errors.append(f'{iid}: dependency cannot reference itself')
            unknown_dep=[x for x in dep_ids if x not in id_set]
            if unknown_dep: errors.append(f'{iid}: unknown dependency improvement ids: {unknown_dep}')
            if not isinstance(d.get('note'),str) or not d.get('note','').strip(): errors.append(f'{iid}: dependency.note is required')

        opts=imp.get('implementation_options') or []
        if not isinstance(opts,list): errors.append(f'{iid}: implementation_options must be a list'); opts=[]
        no_opt_reason=imp.get('implementation_options_reason')
        if not opts:
            if not isinstance(no_opt_reason,str) or not no_opt_reason.strip(): errors.append(f'{iid}: implementation_options_reason is required when implementation_options is empty')
        elif no_opt_reason is not None and (not isinstance(no_opt_reason,str) or not no_opt_reason.strip()):
            errors.append(f'{iid}: implementation_options_reason must be a non-empty string when provided')
        for oi,opt in enumerate(opts,1):
            if not isinstance(opt,dict): errors.append(f'{iid}: implementation option #{oi} must be an object'); continue
            for field in ('product_or_service','capability','role'):
                if not isinstance(opt.get(field),str) or not opt.get(field,'').strip(): errors.append(f'{iid}: implementation option #{oi}.{field} is required')
            if opt.get('fit') not in FIT: errors.append(f'{iid}: implementation option #{oi}.fit must be primary/complementary/alternative')
            if opt.get('confidence') not in QUAL: errors.append(f'{iid}: implementation option #{oi}.confidence must be high/medium/low')
            pre=opt.get('prerequisites') or []
            if pre and not is_str_list(pre): errors.append(f'{iid}: implementation option #{oi}.prerequisites must be a string list')
            refs=opt.get('source_refs') or []
            if refs and not is_str_list(refs): errors.append(f'{iid}: implementation option #{oi}.source_refs must be a string list'); refs=[]
            if not refs:
                warnings.append(f'{iid}: implementation option #{oi} ({opt.get("product_or_service") or "product/service"}) has no source_refs; verify current product capability when possible')
            for ref in refs:
                if ref not in src_ids: errors.append(f'{iid}: implementation option #{oi} unknown source_ref {ref}')

        if any(isinstance(o,dict) and o.get('fit')=='complementary' for o in opts) and not any(isinstance(o,dict) and o.get('fit')=='primary' for o in opts):
            warnings.append(f'{iid}: complementary implementation option normally requires a primary option')

        for field in ('prerequisites','unresolved_questions','source_refs'):
            v=imp.get(field) or []
            if not is_str_list(v) and v != []: errors.append(f'{iid}: {field} must be a string list')
        for ref in imp.get('source_refs') or []:
            if ref not in src_ids: errors.append(f'{iid}: unknown source_ref {ref}')
        ev=imp.get('as_is_evidence') or []
        if not isinstance(ev,list): errors.append(f'{iid}: as_is_evidence must be a list'); ev=[]
        for e in ev:
            if not isinstance(e,dict): errors.append(f'{iid}: as_is_evidence entries must be objects'); continue
            tid=e.get('task_id')
            if tid not in tasks: errors.append(f'{iid}: as_is_evidence unknown task_id {tid}')
            if not isinstance(e.get('note'),str) or not e.get('note','').strip(): errors.append(f'{iid}: as_is_evidence.note is required')

    source_open_questions=((process.get('metadata') or {}).get('open_questions') or [])
    if not isinstance(source_open_questions,list) or not all(isinstance(x,str) and x.strip() for x in source_open_questions):
        errors.append('source process metadata.open_questions must be a string list when present')
        source_open_questions=[]
    coverage=data.get('as_is_open_question_coverage') or []
    if not isinstance(coverage,list):
        errors.append('as_is_open_question_coverage must be a list')
        coverage=[]
    covered_questions=[]
    for ci,c in enumerate(coverage,1):
        if not isinstance(c,dict):
            errors.append(f'as_is_open_question_coverage #{ci} must be an object'); continue
        question=c.get('question')
        if not isinstance(question,str) or not question.strip():
            errors.append(f'as_is_open_question_coverage #{ci}.question is required'); continue
        if question not in source_open_questions:
            errors.append(f'as_is_open_question_coverage #{ci} references unknown source open question: {question}')
        if question in covered_questions:
            errors.append(f'duplicate as_is_open_question_coverage question: {question}')
        covered_questions.append(question)
        imp_ids=c.get('improvement_ids') or []
        if imp_ids and not is_str_list(imp_ids):
            errors.append(f'as_is_open_question_coverage #{ci}.improvement_ids must be a string list'); imp_ids=[]
        unknown_cov=[x for x in imp_ids if x not in id_set]
        if unknown_cov:
            errors.append(f'as_is_open_question_coverage #{ci} unknown improvement ids: {unknown_cov}')
        carried=c.get('carried_forward')
        if not isinstance(carried,bool):
            errors.append(f'as_is_open_question_coverage #{ci}.carried_forward must be true/false')
        if not imp_ids and carried is not True:
            errors.append(f'as_is_open_question_coverage #{ci} must reference at least one improvement or set carried_forward=true')
        if not isinstance(c.get('note'),str) or not c.get('note','').strip():
            errors.append(f'as_is_open_question_coverage #{ci}.note is required')
    missing_cov=[q for q in source_open_questions if q not in covered_questions]
    if missing_cov:
        errors.append(f'missing as_is_open_question_coverage entries: {missing_cov}')


    # Process-pattern coverage: every analysis must explicitly evaluate common cross-process patterns.
    pattern_cov=data.get('process_pattern_coverage') or []
    if not isinstance(pattern_cov,list):
        errors.append('process_pattern_coverage must be a list')
        pattern_cov=[]
    pattern_map={}
    for pi,c in enumerate(pattern_cov,1):
        if not isinstance(c,dict):
            errors.append(f'process_pattern_coverage #{pi} must be an object'); continue
        pattern=c.get('pattern')
        if pattern not in PROCESS_PATTERNS:
            errors.append(f'process_pattern_coverage #{pi}.pattern must be one of {sorted(PROCESS_PATTERNS)}'); continue
        if pattern in pattern_map:
            errors.append(f'duplicate process_pattern_coverage pattern: {pattern}')
        pattern_map[pattern]=c
        present=c.get('present')
        if not isinstance(present,bool):
            errors.append(f'process_pattern_coverage {pattern}.present must be true/false')
        related=c.get('related_tasks') or []
        if related and not is_str_list(related):
            errors.append(f'process_pattern_coverage {pattern}.related_tasks must be a string list'); related=[]
        unknown_related=[x for x in related if x not in tasks]
        if unknown_related:
            errors.append(f'process_pattern_coverage {pattern} unknown related task ids: {unknown_related}')
        imp_ids=c.get('improvement_ids') or []
        if imp_ids and not is_str_list(imp_ids):
            errors.append(f'process_pattern_coverage {pattern}.improvement_ids must be a string list'); imp_ids=[]
        unknown_imp=[x for x in imp_ids if x not in id_set]
        if unknown_imp:
            errors.append(f'process_pattern_coverage {pattern} unknown improvement ids: {unknown_imp}')
        if not isinstance(c.get('note'),str) or not c.get('note','').strip():
            errors.append(f'process_pattern_coverage {pattern}.note is required')
        if present is False and imp_ids:
            errors.append(f'process_pattern_coverage {pattern}: improvement_ids must be empty when present=false')
    missing_patterns=sorted(PROCESS_PATTERNS-set(pattern_map))
    if missing_patterns:
        errors.append(f'missing process_pattern_coverage entries: {missing_patterns}')

    # Deterministic checks for structurally observable patterns.
    nodes=[n for n in (process.get('nodes') or []) if isinstance(n,dict) and n.get('id')]
    node_by_id={str(n.get('id')):n for n in nodes}
    adjacency={nid:[] for nid in node_by_id}
    for e in process.get('edges') or []:
        if not isinstance(e,dict): continue
        a=str(e.get('from') or ''); b=str(e.get('to') or '')
        if a in adjacency and b in node_by_id: adjacency[a].append(b)
    color={}
    def _dfs_cycle(nid):
        color[nid]=1
        for nxt in adjacency.get(nid,[]):
            if color.get(nxt)==1: return True
            if color.get(nxt,0)==0 and _dfs_cycle(nxt): return True
        color[nid]=2
        return False
    has_loop=any(color.get(nid,0)==0 and _dfs_cycle(nid) for nid in node_by_id)
    if has_loop and (pattern_map.get('loop') or {}).get('present') is not True:
        errors.append('process_pattern_coverage loop.present must be true because the As-Is graph contains a cycle')
    has_parallel=any(n.get('type')=='gateway_parallel' for n in nodes)
    if has_parallel and (pattern_map.get('parallel_dependency') or {}).get('present') is not True:
        errors.append('process_pattern_coverage parallel_dependency.present must be true because the As-Is process contains parallel gateways')

    # Handoff detection follows paths from one task through gateways/events to the next task(s).
    task_nodes={str(n.get('id')):n for n in nodes if n.get('type')=='task'}
    has_handoff=False
    for tid,t in task_nodes.items():
        start_p=t.get('participant')
        stack=list(adjacency.get(tid,[])); seen=set()
        while stack and not has_handoff:
            x=stack.pop()
            if x in seen: continue
            seen.add(x)
            xn=node_by_id.get(x) or {}
            if xn.get('type')=='task':
                if start_p and xn.get('participant') and xn.get('participant')!=start_p:
                    has_handoff=True
                continue
            stack.extend(adjacency.get(x,[]))
        if has_handoff: break
    if has_handoff and (pattern_map.get('handoff') or {}).get('present') is not True:
        errors.append('process_pattern_coverage handoff.present must be true because the As-Is process contains cross-participant handoffs')

    oq=data.get('analysis_open_questions') or []
    if not is_str_list(oq) and oq != []: errors.append('analysis_open_questions must be a string list')
    return errors,warnings

def _analysis_id(data):
    payload={k:v for k,v in data.items() if k!='analysis_id'}
    canonical=json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',',':'))
    return 'bpr-a-'+hashlib.sha256(canonical.encode('utf-8')).hexdigest()[:16]

def normalize(data, stamp_id=False):
    imps=data.get('improvements') or []
    data['summary']={
        'improvement_count': len(imps),
        'task_scope_count': sum(1 for x in imps if x.get('scope')=='task'),
        'process_scope_count': sum(1 for x in imps if x.get('scope')=='process'),
        'high_impact_count': sum(1 for x in imps if (x.get('expected_effect') or {}).get('impact')=='high'),
        'analysis_open_question_count': len(data.get('analysis_open_questions') or []),
        'implementation_option_count': sum(len(x.get('implementation_options') or []) for x in imps if isinstance(x,dict)),
        'as_is_open_question_coverage_count': len(data.get('as_is_open_question_coverage') or []),
        'process_pattern_coverage_count': len(data.get('process_pattern_coverage') or []),
        'process_pattern_present_count': sum(1 for x in (data.get('process_pattern_coverage') or []) if isinstance(x,dict) and x.get('present') is True),
    }
    expected=_analysis_id(data)
    if stamp_id:
        data['analysis_id']=expected
    else:
        data.setdefault('_expected_analysis_id', expected)
    return data

def main():
    ap=argparse.ArgumentParser()
    sp=ap.add_subparsers(dest='cmd',required=True)
    w=sp.add_parser('write'); w.add_argument('--process',required=True); w.add_argument('--output',required=True); w.add_argument('--json')
    v=sp.add_parser('validate'); v.add_argument('--process',required=True); v.add_argument('--input',required=True)
    args=ap.parse_args()
    process=load_yaml(args.process)
    data=read_json(args) if args.cmd=='write' else load_yaml(args.input)
    data=normalize(data, stamp_id=(args.cmd=='write'))
    expected=data.pop('_expected_analysis_id', None)
    errors,warnings=validate(data,process)
    if args.cmd=='validate' and expected and data.get('analysis_id')!=expected:
        errors.append(f"analysis_id does not match analysis content: expected {expected}")
    result={'ok':not errors,'errors':errors,'warnings':warnings,'summary':data.get('summary',{})}
    if args.cmd=='write' and not errors:
        dump_yaml(data,args.output); result['output']=args.output
    print(json.dumps(result,ensure_ascii=False,indent=2))
    sys.exit(0 if not errors else 2)
if __name__=='__main__': main()
