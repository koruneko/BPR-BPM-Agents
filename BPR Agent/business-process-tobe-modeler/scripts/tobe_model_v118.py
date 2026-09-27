#!/usr/bin/env python3
import argparse, json, re, sys
import yaml

VALID_DECISIONS={'approved','conditional_approved','hold','rejected'}
ACTIVE_DECISIONS={'approved','conditional_approved'}


def load_yaml(path):
    with open(path,encoding='utf-8') as f:return yaml.safe_load(f)
def dump_yaml(data,path):
    with open(path,'w',encoding='utf-8',newline='\n') as f:yaml.safe_dump(data,f,allow_unicode=True,sort_keys=False,width=120)
def read_json(args):
    if args.json:return json.loads(args.json)
    txt=sys.stdin.read()
    if not txt.strip(): raise ValueError('JSON input is empty')
    return json.loads(txt)
def node_map(proc):return {x.get('id'):x for x in proc.get('nodes') or [] if isinstance(x,dict) and x.get('id')}
def edge_map(proc):return {x.get('id'):x for x in proc.get('edges') or [] if isinstance(x,dict) and x.get('id')}

def _unknown_keys(obj, allowed, path, errors):
    if not isinstance(obj,dict):
        return
    extra=sorted(set(obj)-set(allowed))
    for key in extra:
        errors.append(f'unknown_schema_key at {path}: {key}')

def strict_schema_errors(data):
    """Reject structurally valid YAML that contains keys outside schema v1.0/BPR extensions."""
    errors=[]
    if not isinstance(data,dict):
        return ['schema root must be an object']
    _unknown_keys(data, {'schema_version','process','participants','nodes','edges','metadata'}, '$', errors)
    proc=data.get('process')
    if isinstance(proc,dict):
        _unknown_keys(proc, {'id','name','description','owner','version','scope'}, '$.process', errors)
        if isinstance(proc.get('scope'),dict):
            _unknown_keys(proc['scope'], {'start','end'}, '$.process.scope', errors)
    for i,x in enumerate(data.get('participants') or []):
        if isinstance(x,dict): _unknown_keys(x, {'id','name','type'}, f'$.participants[{i}]', errors)
    node_allowed={'id','type','name','participant','task_type','description','system','inputs','outputs','duration','frequency','issues','automation'}
    for i,x in enumerate(data.get('nodes') or []):
        if not isinstance(x,dict): continue
        _unknown_keys(x,node_allowed,f'$.nodes[{i}]',errors)
        if isinstance(x.get('automation'),dict):
            _unknown_keys(x['automation'], {'candidate','level','notes','exception_owner'}, f'$.nodes[{i}].automation', errors)
    for i,x in enumerate(data.get('edges') or []):
        if isinstance(x,dict): _unknown_keys(x, {'id','from','to','name','condition','default'}, f'$.edges[{i}]', errors)
    meta=data.get('metadata')
    if isinstance(meta,dict):
        _unknown_keys(meta, {'assumptions','open_questions','inferences','bpr'}, '$.metadata', errors)
        bpr=meta.get('bpr')
        if isinstance(bpr,dict):
            _unknown_keys(bpr, {'source_process','source_analysis_version','source_analysis_id','applied_improvements','conditional_improvements','change_log','source_node_context','performance_targets','issue_disposition','open_question_disposition'}, '$.metadata.bpr', errors)
            if isinstance(bpr.get('source_process'),dict):
                _unknown_keys(bpr['source_process'], {'id','name','version'}, '$.metadata.bpr.source_process', errors)
            for i,x in enumerate(bpr.get('conditional_improvements') or []):
                if isinstance(x,dict): _unknown_keys(x, {'improvement_id','condition'}, f'$.metadata.bpr.conditional_improvements[{i}]', errors)
            for i,x in enumerate(bpr.get('change_log') or []):
                if not isinstance(x,dict): continue
                _unknown_keys(x, {'improvement_id','title','action','summary','expected_effect','confidence','condition','source_node_ids','target_node_ids','source_edge_ids','target_edge_ids'}, f'$.metadata.bpr.change_log[{i}]', errors)
                if isinstance(x.get('expected_effect'),dict):
                    _unknown_keys(x['expected_effect'], {'impact','notes'}, f'$.metadata.bpr.change_log[{i}].expected_effect', errors)
            for i,x in enumerate(bpr.get('performance_targets') or []):
                if isinstance(x,dict): _unknown_keys(x, {'metric','baseline','target','direction','note','related_improvements','source_node_ids','target_node_ids'}, f'$.metadata.bpr.performance_targets[{i}]', errors)
            for i,x in enumerate(bpr.get('open_question_disposition') or []):
                if isinstance(x,dict): _unknown_keys(x, {'source','question','status','materiality','resolution','note'}, f'$.metadata.bpr.open_question_disposition[{i}]', errors)
            idisp=bpr.get('issue_disposition')
            if isinstance(idisp,dict):
                for nid,entries in idisp.items():
                    for i,x in enumerate(entries or []):
                        if isinstance(x,dict): _unknown_keys(x, {'source_issue','status','to_be_issue','performance_target_metric','note'}, f'$.metadata.bpr.issue_disposition.{nid}[{i}]', errors)
            sctx=bpr.get('source_node_context')
            if isinstance(sctx,dict):
                for nid,x in sctx.items():
                    if isinstance(x,dict): _unknown_keys(x, {'name','participant','system','duration','frequency','issues'}, f'$.metadata.bpr.source_node_context.{nid}', errors)
    return errors



def _semantic_text(improvement):
    parts=[]
    for key in ('title','rationale','proposed_change'):
        v=improvement.get(key)
        if isinstance(v,str): parts.append(v)
    for key in ('prerequisites','unresolved_questions'):
        vals=improvement.get(key) or []
        if isinstance(vals,list): parts.extend(str(x) for x in vals)
    for ev in improvement.get('as_is_evidence') or []:
        if isinstance(ev,dict) and isinstance(ev.get('note'),str): parts.append(ev['note'])
    for opt in improvement.get('implementation_options') or []:
        if not isinstance(opt,dict): continue
        for key in ('product_or_service','capability','role'):
            v=opt.get(key)
            if isinstance(v,str): parts.append(v)
        vals=opt.get('prerequisites') or []
        if isinstance(vals,list): parts.extend(str(x) for x in vals)
    return '\n'.join(parts)

def _norm_semantic(s):
    return re.sub(r'[\s、。・/／（）()「」『』：:,.!?！？\-_\[\]]+', '', str(s or '')).lower()

def _char_ngrams(s,n=3):
    s=_norm_semantic(s)
    if len(s)<n: return set()
    return {s[i:i+n] for i in range(len(s)-n+1)}

def _condition_alignment(note, own_id, improvements):
    """Conservative lexical guardrail. Semantic review by the agent remains mandatory."""
    note_norm=_norm_semantic(note)
    if len(note_norm)<12: return None
    ng=_char_ngrams(note)
    if not ng: return None
    scores={}
    for iid,imp in improvements.items():
        ig=_char_ngrams(_semantic_text(imp))
        scores[iid]=(len(ng & ig)/len(ng)) if ig else 0.0
    own=scores.get(own_id,0.0)
    others=[(score,iid) for iid,score in scores.items() if iid!=own_id]
    if not others: return None
    best,best_id=max(others)
    if own < 0.12 and best >= 0.32 and (best-own) >= 0.20:
        return {'own_score':own,'best_other_score':best,'best_other_id':best_id}
    return None



def _all_analysis_questions(source, analysis, active_ids):
    """Return canonical unresolved questions that must be dispositioned in the To-Be.

    Source open questions already mapped to an active improvement by
    as_is_open_question_coverage are represented by that improvement's more
    actionable unresolved_questions, avoiding duplicate Human Gate prompts.
    """
    out=[]
    seen=set()
    active_set=set(active_ids)
    covered_source=set()
    for cov in analysis.get('as_is_open_question_coverage') or []:
        if not isinstance(cov,dict):
            continue
        if active_set.intersection(set(cov.get('improvement_ids') or [])):
            q=str(cov.get('question') or '').strip()
            if q:
                covered_source.add(q)
    def add(q, source_kind, improvement_id=None):
        q=str(q or '').strip()
        if not q or q in seen:
            return
        seen.add(q)
        source_ref=str(improvement_id) if improvement_id else source_kind
        out.append({'question':q,'source':source_kind,'source_ref':source_ref,'improvement_id':improvement_id})
    for iid in active_ids:
        imp=next((x for x in (analysis.get('improvements') or []) if isinstance(x,dict) and x.get('id')==iid),{})
        for q in imp.get('unresolved_questions') or []:
            add(q,'improvement',iid)
    for q in ((source.get('metadata') or {}).get('open_questions') or []):
        if str(q or '').strip() not in covered_source:
            add(q,'as_is')
    for q in analysis.get('analysis_open_questions') or []:
        add(q,'analysis')
    return out

def _is_material_business_rule_question(question):
    """Return True only when the unresolved answer is needed to choose one product-neutral control flow.

    Numeric/timing parameters (for example retry count or SLA) and implementation details
    are intentionally non-blocking when the model can preserve them as open parameters.
    Agent semantic review may still classify an additional question as blocking when its
    answer actually changes topology, branch semantics, or the primary actor.
    """
    q=str(question or '')
    patterns=[
        r'上限到達.*?(?:経路|どの|どこ|却下|相談|確認|進め)',
        r'(?:非承認|承認しない).*?(?:却下|差し戻し|経路|終了|振込対象)',
        r'差し戻し先.*?(?:社員|上長|経理|どこ)',
        r'非承認申請.*?(?:振込対象|終了|状態)',
        r'(?:外貨|税抜|税込|支払金額|どの金額).*?(?:閾値|判定)',
        r'(?:閾値|判定).*?(?:外貨|税抜|税込|支払金額|どの金額)',
        r'職務分離', r'二重承認',
    ]
    return any(re.search(p,q,re.I) for p in patterns)


def _grouped_resolution_expansion_errors(question_items, resolution_map):
    """Detect Human Gate answers that semantically settle more than one source question.

    A grouped user-facing question may be convenient, but improvement-decisions.yaml remains
    source-question granular. If one answer clearly resolves another unresolved question from
    the same improvement, require an explicit business_rule_resolutions entry for that original
    question instead of silently leaving it carried forward.
    """
    errors=[]
    by_source={}
    for item in question_items:
        by_source.setdefault(str(item.get('source_ref') or ''), []).append(str(item.get('question') or '').strip())
    resolutions_by_source={}
    for q,entry in resolution_map.items():
        resolutions_by_source.setdefault(str(entry.get('source') or ''), []).append(str(entry.get('resolution') or ''))
    for source_ref, questions in by_source.items():
        joined=' '.join(resolutions_by_source.get(source_ref, []))
        if not joined:
            continue
        for q in questions:
            if q in resolution_map:
                continue
            implied=False
            if re.search(r'最大回数を設けるか|上限回数を設けるか', q) and re.search(r'上限.*(?:達|超|設け)|再申請.*上限', joined):
                implied=True
            if re.search(r'(?:どのTask|どのタスク|どこ).*戻', q) and re.search(r'(?:上長|申請者|社員|部門長|経理).*?(?:確認|申請|Task|タスク)?へ?戻', joined):
                implied=True
            if implied:
                errors.append(
                    f'grouped_business_rule_resolution_not_expanded [{source_ref}]: {q} | '
                    'the grouped Human Gate answer also resolves this original question; add one business_rule_resolutions entry per original unresolved question'
                )
    return errors


def _question_appears_resolved_by_model(question, tobe):
    """Conservative checks for carried-forward questions contradicted by explicit To-Be topology."""
    q=str(question or '')
    nodes=[n for n in (tobe.get('nodes') or []) if isinstance(n,dict)]
    edges=[e for e in (tobe.get('edges') or []) if isinstance(e,dict)]
    node_map={str(n.get('id')):n for n in nodes if n.get('id')}
    if re.search(r'最大回数を設けるか|上限回数を設けるか', q):
        text=' '.join(str(n.get('name') or '')+' '+str(n.get('description') or '') for n in nodes)
        text+=' '+' '.join(str(e.get('name') or '')+' '+str(e.get('condition') or '') for e in edges)
        return bool(re.search(r'再申請.*上限|上限.*再申請', text))
    if re.search(r'(?:どのTask|どのタスク|どこ).*戻', q):
        for e in edges:
            src=node_map.get(str(e.get('from') or ''),{})
            dst=node_map.get(str(e.get('to') or ''),{})
            st=(str(src.get('name') or '')+' '+str(src.get('description') or ''))
            dt=(str(dst.get('name') or '')+' '+str(dst.get('description') or ''))
            if '差し戻' in st and re.search(r'再申請|確認|申請',dt):
                return True
    return False


def _validate_branch_exception_paths(tobe, analysis, active_ids):
    """Require automated parallel branches to model success vs exception before a parallel join."""
    errors=[]
    nodes=[n for n in (tobe.get('nodes') or []) if isinstance(n,dict) and n.get('id')]
    edges=[e for e in (tobe.get('edges') or []) if isinstance(e,dict)]
    node_map={str(n['id']):n for n in nodes}
    outgoing={nid:[] for nid in node_map}; incoming={nid:[] for nid in node_map}
    for e in edges:
        src,dst=str(e.get('from') or ''),str(e.get('to') or '')
        if src in outgoing: outgoing[src].append(e)
        if dst in incoming: incoming[dst].append(e)
    imp_text=' '.join(
        str(x.get('proposed_change') or '')+' '+str(x.get('rationale') or '')
        for x in (analysis.get('improvements') or []) if isinstance(x,dict) and x.get('id') in set(active_ids)
    )
    needs_stall_control='滞留' in imp_text or '期限超過' in imp_text
    for n in nodes:
        if n.get('type')!='task' or n.get('task_type') not in {'service','script'}:
            continue
        auto=n.get('automation') if isinstance(n.get('automation'),dict) else {}
        owner=str(auto.get('exception_owner') or '')
        if not owner:
            continue
        nid=str(n['id']); outs=outgoing.get(nid,[])
        if len(outs)!=1:
            errors.append(f'{nid}: automated task with exception_owner must route to one explicit result gateway before normal/exception continuation')
            continue
        gate=node_map.get(str(outs[0].get('to') or ''),{})
        gid=str(gate.get('id') or '')
        if gate.get('type')!='gateway_exclusive' or len(outgoing.get(gid,[]))<2:
            if gate.get('type')=='gateway_parallel' and len(incoming.get(gid,[]))>1:
                errors.append(f'{nid}: exception-capable automated branch must not connect directly to parallel join {gid}; add a success/failure result gateway before the join')
            else:
                errors.append(f'{nid}: exception_owner is set but success/failure Control Flow is not explicit; add an Exclusive Gateway after the automated attempt')
            continue
        branch_edges=outgoing.get(gid,[])
        success=[e for e in branch_edges if re.search(r'成功|正常', str(e.get('name') or '')+' '+str(e.get('condition') or ''))]
        failure=[e for e in branch_edges if re.search(r'失敗|例外|エラー|滞留|期限|タイムアウト', str(e.get('name') or '')+' '+str(e.get('condition') or '')) or e.get('default') is True]
        if not success or not failure:
            errors.append(f'{nid}: result gateway {gid} must have explicit success and failure/exception branches')
            continue
        owner_ok=False
        for e in failure:
            target=node_map.get(str(e.get('to') or ''),{})
            if str(target.get('participant') or '')==owner:
                owner_ok=True
        if not owner_ok:
            errors.append(f'{nid}: failure/exception branch must route to a task owned by automation.exception_owner={owner}')
        if needs_stall_control:
            labels=' '.join(str(e.get('name') or '')+' '+str(e.get('condition') or '') for e in failure)
            if not re.search(r'滞留|期限|タイムアウト|失敗|例外', labels):
                errors.append(f'{nid}: active improvements require failure/stall control, but result gateway {gid} has no exception/timeout semantics')
    return errors

def _business_rule_resolution_map(decisions):
    entries=decisions.get('business_rule_resolutions') or []
    out={}; errors=[]
    if entries is not None and not isinstance(entries,list):
        return out,['business_rule_resolutions must be a list when present']
    for i,e in enumerate(entries or [],1):
        if not isinstance(e,dict):
            errors.append(f'business_rule_resolutions entry #{i} must be an object'); continue
        q=str(e.get('question') or '').strip(); source_ref=str(e.get('source') or '').strip(); resolution=str(e.get('resolution') or '').strip()
        if not q: errors.append(f'business_rule_resolutions entry #{i}: question is required'); continue
        if q in out: errors.append(f'duplicate business_rule_resolutions question: {q}')
        if not resolution: errors.append(f'business_rule_resolutions entry #{i}: resolution is required')
        
        if not source_ref: errors.append(f'business_rule_resolutions entry #{i}: source is required')
        out[q]={'resolution':resolution,'source':source_ref}
    return out,errors

def source_task_context(source):
    out={}
    for n in source.get('nodes') or []:
        if not isinstance(n,dict) or n.get('type')!='task' or not n.get('id'):
            continue
        ctx={'name': n.get('name') or n.get('id')}
        for key in ('participant','system','duration','frequency'):
            if n.get(key) not in (None,''):
                ctx[key]=n.get(key)
        issues=n.get('issues')
        ctx['issues']=list(issues) if isinstance(issues,list) else []
        out[str(n['id'])]=ctx
    return out

def enrich_tobe(tobe,source,analysis):
    meta=tobe.setdefault('metadata',{}).setdefault('bpr',{})
    # Source snapshots are deterministic provenance, not model-authored facts.
    meta['source_node_context']=source_task_context(source)
    meta['source_analysis_id']=analysis.get('analysis_id')
    meta.setdefault('performance_targets',[])
    meta.setdefault('issue_disposition',{})
    meta.setdefault('open_question_disposition',[])
    return tobe


def validate_decisions(decisions,analysis,source):
    errors=[];warnings=[]
    if str(decisions.get('decision_version'))!='1.3':errors.append('decision_version must be 1.3')
    if str(decisions.get('source_analysis_version'))!=str(analysis.get('analysis_version')):errors.append('source_analysis_version mismatch')
    if decisions.get('source_analysis_id')!=analysis.get('analysis_id'):errors.append('source_analysis_id mismatch; Human Gate decisions must target the exact improvement analysis artifact')
    sp=decisions.get('source_process') or {}; srcp=source.get('process') or {}
    if sp.get('id')!=srcp.get('id') or str(sp.get('version'))!=str(srcp.get('version')):errors.append('decision source_process mismatch')
    improvements={x.get('id'):x for x in analysis.get('improvements') or [] if isinstance(x,dict)}
    valid_ids=set(improvements)
    seen=set(); active=[]; conditional=[]; decision_map={}
    for d in decisions.get('decisions') or []:
        if not isinstance(d,dict):errors.append('decision entry must be object');continue
        iid=d.get('improvement_id'); dec=d.get('decision'); note=(d.get('note') or '').strip() if isinstance(d.get('note'),str) else ''
        if iid not in valid_ids:errors.append(f'unknown improvement_id in decisions: {iid}')
        if iid in seen:errors.append(f'duplicate decision for {iid}')
        seen.add(iid)
        if dec not in VALID_DECISIONS:errors.append(f'{iid}: decision must be approved/conditional_approved/hold/rejected')
        decision_map[iid]=dec
        selected=d.get('selected_implementation_options')
        if selected is not None:
            if not isinstance(selected,list) or not selected or not all(isinstance(x,str) and x.strip() for x in selected):
                errors.append(f'{iid}: selected_implementation_options must be a non-empty string list when provided')
            else:
                valid_products={str(o.get('product_or_service')).strip() for o in (improvements.get(iid) or {}).get('implementation_options') or [] if isinstance(o,dict) and o.get('product_or_service')}
                unknown_sel=[x for x in selected if x not in valid_products]
                if unknown_sel: errors.append(f'{iid}: selected_implementation_options contains unknown candidate(s): {unknown_sel}')
                if dec not in ACTIVE_DECISIONS: errors.append(f'{iid}: implementation product selection requires approved or conditional_approved decision')
        if dec in ACTIVE_DECISIONS:active.append(iid)
        if dec=='conditional_approved':
            if not note:
                errors.append(f'{iid}: conditional_approved requires a non-empty note describing the condition')
            elif iid in improvements:
                mismatch=_condition_alignment(note,iid,improvements)
                if mismatch:
                    errors.append(
                        f"{iid}: conditional approval note may be semantically bound to {mismatch['best_other_id']} rather than {iid}; "
                        'confirm/correct the Human Gate decision before To-Be generation'
                    )
            conditional.append({'improvement_id':iid,'condition':note})
    active_set=set(active)
    for iid in active:
        imp=improvements.get(iid) or {}
        for dep in imp.get('dependencies') or []:
            typ=dep.get('type'); deps=set(dep.get('improvement_ids') or [])
            if typ=='requires' and not deps.issubset(active_set):
                errors.append(f'{iid}: requires active improvements {sorted(deps)}, active={sorted(active_set)}')
            elif typ=='any_of' and deps and not (deps & active_set):
                errors.append(f'{iid}: requires at least one of {sorted(deps)} to be approved or conditionally approved')
            elif typ=='enhances':
                # Informational relationship only. It must never block To-Be generation
                # and should not create warning noise when the enhancing proposal is not selected.
                pass

    # Material Business Rule Gate: adopting an improvement does not decide unresolved
    # rules that change topology, branch semantics, exception routing, or responsibility.
    resolution_map,br_errors=_business_rule_resolution_map(decisions)
    errors.extend(br_errors)
    question_items=_all_analysis_questions(source,analysis,active)
    known_questions={x['question']:x for x in question_items}
    errors.extend(_grouped_resolution_expansion_errors(question_items,resolution_map))
    for q,res in resolution_map.items():
        item=known_questions.get(q)
        if not item:
            errors.append(f'business_rule_resolutions references an unknown unresolved question: {q}')
            continue
        if res.get('source') != item.get('source_ref'):
            errors.append(f'business_rule_resolutions source mismatch for question: {q}; expected {item.get("source_ref")}, actual {res.get("source")}')
    for item in question_items:
        q=item['question']
        if _is_material_business_rule_question(q) and q not in resolution_map:
            errors.append(
                f'material_business_rule_unresolved [{item.get("source_ref")}]: {q} | '
                'confirm the business rule in Human Gate and add business_rule_resolutions before To-Be generation'
            )
    return errors,warnings,active,conditional


def validate_tobe(tobe,source,analysis,decisions):
    errors=[];warnings=[]
    errors.extend(strict_schema_errors(tobe))
    de,dw,active,conditional=validate_decisions(decisions,analysis,source);errors.extend(de);warnings.extend(dw)
    srcp=source.get('process') or {}; tp=tobe.get('process') or {}
    improvements={x.get('id'):x for x in analysis.get('improvements') or [] if isinstance(x,dict) and x.get('id')}
    if not tp.get('id'):errors.append('To-Be process.id is required')
    if tp.get('id')==srcp.get('id'):errors.append('To-Be process.id must differ from As-Is process.id')
    if not isinstance(tobe.get('nodes'),list) or not isinstance(tobe.get('edges'),list):errors.append('To-Be nodes/edges must be lists')
    meta=((tobe.get('metadata') or {}).get('bpr') or {})
    msp=meta.get('source_process') or {}
    if msp.get('id')!=srcp.get('id') or str(msp.get('version'))!=str(srcp.get('version')):errors.append('metadata.bpr.source_process must match As-Is')
    if str(meta.get('source_analysis_version'))!=str(analysis.get('analysis_version')):errors.append('metadata.bpr.source_analysis_version mismatch')
    if meta.get('source_analysis_id')!=analysis.get('analysis_id'):errors.append('metadata.bpr.source_analysis_id must match improvement analysis analysis_id')
    expected_source_ctx=source_task_context(source)
    source_ctx=meta.get('source_node_context') or {}
    if source_ctx != expected_source_ctx:
        errors.append('metadata.bpr.source_node_context must exactly preserve As-Is task name/participant/system/duration/frequency/issues')
    performance_targets=meta.get('performance_targets')
    if performance_targets is None:
        errors.append('metadata.bpr.performance_targets is required and must be a list')
        performance_targets=[]
    elif not isinstance(performance_targets,list):
        errors.append('metadata.bpr.performance_targets must be a list'); performance_targets=[]
    issue_disposition=meta.get('issue_disposition') or {}
    if not isinstance(issue_disposition,dict):
        errors.append('metadata.bpr.issue_disposition must be an object'); issue_disposition={}
    open_question_disposition=meta.get('open_question_disposition')
    if open_question_disposition is None:
        errors.append('metadata.bpr.open_question_disposition is required and must cover every relevant unresolved question')
        open_question_disposition=[]
    elif not isinstance(open_question_disposition,list):
        errors.append('metadata.bpr.open_question_disposition must be a list'); open_question_disposition=[]

    expected_questions=_all_analysis_questions(source,analysis,active)
    expected_qset={x['question'] for x in expected_questions}
    resolution_map,_=_business_rule_resolution_map(decisions)
    oq_map={}
    allowed_oq_status={'resolved','carried_forward','not_applicable'}
    for i,e in enumerate(open_question_disposition,1):
        if not isinstance(e,dict):
            errors.append(f'open_question_disposition entry #{i} must be an object'); continue
        q=str(e.get('question') or '').strip(); status=e.get('status'); source_ref=str(e.get('source') or '').strip(); materiality=e.get('materiality'); note=str(e.get('note') or '').strip()
        if not q:
            errors.append(f'open_question_disposition entry #{i}: question is required'); continue
        if q in oq_map: errors.append(f'duplicate open_question_disposition question: {q}')
        if q not in expected_qset:
            if source_ref != 'design':
                errors.append(f'open_question_disposition references unknown question: {q}; To-Be-introduced questions must use source=design')
        else:
            expected_item=next(x for x in expected_questions if x['question']==q)
            if source_ref != expected_item.get('source_ref'):
                errors.append(f'{q}: open_question_disposition.source mismatch; expected {expected_item.get("source_ref")}, actual {source_ref}')
        if status not in allowed_oq_status: errors.append(f'{q}: open_question_disposition.status must be resolved/carried_forward/not_applicable')
        if not source_ref: errors.append(f'{q}: open_question_disposition.source is required')
        if materiality not in {'blocking','non_blocking'}: errors.append(f'{q}: open_question_disposition.materiality must be blocking/non_blocking')
        if not note: errors.append(f'{q}: open_question_disposition.note is required')
        resolution=str(e.get('resolution') or '').strip()
        if status=='resolved' and not resolution:
            errors.append(f'{q}: resolved open question requires resolution')
        if status=='carried_forward' and materiality=='blocking':
            errors.append(f'{q}: blocking open question cannot be carried_forward in a Final To-Be')
        if q in resolution_map:
            if status!='resolved': errors.append(f'{q}: Human Gate business rule resolution exists, so disposition must be resolved')
            if resolution != resolution_map[q]['resolution']: errors.append(f'{q}: disposition resolution must exactly preserve business_rule_resolutions resolution')
        if _is_material_business_rule_question(q) and status=='carried_forward':
            errors.append(f'{q}: material business rule affecting topology/branch/actor cannot remain unresolved in Final To-Be')
        if q in expected_qset and status=='carried_forward' and _question_appears_resolved_by_model(q,tobe):
            errors.append(f'{q}: open_question_semantically_resolved; To-Be topology already commits to an answer. Mark the original question resolved and, if a parameter remains unknown, add a new source=design carried_forward question for that parameter.')
        oq_map[q]=e
    missing_q=[q for q in expected_qset if q not in oq_map]
    if missing_q: errors.append(f'open_question_disposition is missing questions: {missing_q}')
    top_open=((tobe.get('metadata') or {}).get('open_questions') or [])
    if not isinstance(top_open,list):
        errors.append('metadata.open_questions must be a list'); top_open=[]
    carried={q for q,e in oq_map.items() if isinstance(e,dict) and e.get('status')=='carried_forward'}
    top_set={str(x).strip() for x in top_open if str(x).strip()}
    if carried != top_set:
        errors.append(f'metadata.open_questions must exactly equal carried_forward open questions. expected={sorted(carried)}, actual={sorted(top_set)}')
    applied=meta.get('applied_improvements') or []
    if set(applied)!=set(active):errors.append(f'applied_improvements must exactly match approved/conditional decisions. active={active}, applied={applied}')
    if len(applied)!=len(set(applied)):errors.append('applied_improvements contains duplicates')

    meta_cond=meta.get('conditional_improvements') or []
    expected_cond={x['improvement_id']:x['condition'] for x in conditional}
    actual_cond={}
    if not isinstance(meta_cond,list):errors.append('metadata.bpr.conditional_improvements must be a list');meta_cond=[]
    for c in meta_cond:
        if not isinstance(c,dict):errors.append('conditional_improvements entry must be object');continue
        iid=c.get('improvement_id'); condition=c.get('condition')
        if not isinstance(condition,str) or not condition.strip():errors.append(f'{iid}: conditional_improvements.condition is required')
        actual_cond[iid]=condition.strip() if isinstance(condition,str) else condition
    if actual_cond!=expected_cond:errors.append(f'conditional_improvements must exactly preserve conditional approval notes. expected={expected_cond}, actual={actual_cond}')

    change=meta.get('change_log') or []
    if not isinstance(change,list):errors.append('metadata.bpr.change_log must be a list');change=[]
    covered_nodes=set();covered_edges=set();change_ids=set()
    for c in change:
        if not isinstance(c,dict):errors.append('change_log entry must be object');continue
        iid=c.get('improvement_id')
        if iid not in active:errors.append(f'change_log references non-active improvement {iid}')
        else:change_ids.add(iid)
        if not isinstance(c.get('summary'),str) or not c.get('summary','').strip():errors.append(f'{iid}: change_log.summary required')
        imp=improvements.get(iid) or {}
        if c.get('title') != imp.get('title'):
            errors.append(f'{iid}: change_log.title must exactly copy improvement title')
        if c.get('expected_effect') != (imp.get('expected_effect') or {}):
            errors.append(f'{iid}: change_log.expected_effect must exactly copy analysis expected_effect')
        expected_conf=(imp.get('priority') or {}).get('confidence')
        if c.get('confidence') != expected_conf:
            errors.append(f'{iid}: change_log.confidence must exactly copy analysis priority.confidence')
        expected_condition=expected_cond.get(iid)
        actual_condition=c.get('condition')
        if expected_condition is not None:
            if actual_condition != expected_condition:
                errors.append(f'{iid}: change_log.condition must exactly preserve conditional approval note')
        elif actual_condition not in (None,''):
            errors.append(f'{iid}: unconditional approval must use null/empty change_log.condition')
        for k in ('source_node_ids','target_node_ids'):
            vals=c.get(k) or []
            if not isinstance(vals,list) or not all(isinstance(x,str) for x in vals):errors.append(f'{iid}: {k} must be a string list')
            else:covered_nodes.update(vals)
        for k in ('source_edge_ids','target_edge_ids'):
            vals=c.get(k) or []
            if not isinstance(vals,list) or not all(isinstance(x,str) for x in vals):errors.append(f'{iid}: {k} must be a string list')
            else:covered_edges.update(vals)
    missing_change=[x for x in active if x not in change_ids]
    if missing_change:errors.append(f'each approved/conditional improvement needs a change_log entry: {missing_change}')
    sm=node_map(source);tm=node_map(tobe); se=edge_map(source);te=edge_map(tobe)

    # To-Be top-level assumptions describe future design premises, not copied As-Is
    # workload/measurement calculations. Baselines belong in source_node_context and
    # performance_targets. Exact carry-over is treated as an error.
    src_assumptions=((source.get('metadata') or {}).get('assumptions') or [])
    tobe_assumptions=((tobe.get('metadata') or {}).get('assumptions') or [])
    if not isinstance(tobe_assumptions,list):
        errors.append('metadata.assumptions must be a list when present')
        tobe_assumptions=[]
    src_assumption_set={str(x).strip() for x in src_assumptions if str(x).strip()} if isinstance(src_assumptions,list) else set()
    copied=[str(x).strip() for x in tobe_assumptions if str(x).strip() in src_assumption_set]
    if copied:
        errors.append(f'To-Be metadata.assumptions must not copy As-Is calculation/baseline assumptions verbatim; keep baselines in source_node_context/performance_targets: {copied}')

    # Execution actor and human exception responsibility are separate concepts.
    # In this BPR To-Be convention, automated service/script tasks use a system
    # participant; a human responsible for exceptions is recorded separately.
    participant_types={str(p.get('id')):str(p.get('type') or '') for p in (tobe.get('participants') or []) if isinstance(p,dict) and p.get('id')}
    for n in tobe.get('nodes') or []:
        if not isinstance(n,dict) or n.get('type')!='task' or n.get('task_type') not in {'service','script'}:
            continue
        nid=str(n.get('id') or '')
        pid=str(n.get('participant') or '')
        if participant_types.get(pid)!='system':
            errors.append(f'{nid}: automated {n.get("task_type")} task participant must reference a participant with type=system; keep human exception responsibility in automation.exception_owner')
        auto=n.get('automation') or {}
        if not isinstance(auto,dict):
            errors.append(f'{nid}: automation must be an object when present')
            continue
        ex=auto.get('exception_owner')
        if ex not in (None,''):
            exid=str(ex)
            if exid not in participant_types:
                errors.append(f'{nid}: automation.exception_owner references unknown participant: {exid}')
            elif participant_types.get(exid)=='system':
                errors.append(f'{nid}: automation.exception_owner must reference a human/organizational participant, not a system participant: {exid}')

    # Parallel control gateways that directly coordinate at least one system-executed
    # branch should live in a system lane. This prevents the diagram from implying that
    # a human role executes the split/join control itself. Purely human parallel work is
    # intentionally left unchanged.
    for n in tobe.get('nodes') or []:
        if not isinstance(n,dict) or n.get('type')!='gateway_parallel' or not n.get('id'):
            continue
        gid=str(n.get('id')); adjacent=[]
        for e in (tobe.get('edges') or []):
            if not isinstance(e,dict): continue
            if str(e.get('from') or '')==gid:
                adjacent.append(tm.get(str(e.get('to') or '')) or {})
            if str(e.get('to') or '')==gid:
                adjacent.append(tm.get(str(e.get('from') or '')) or {})
        has_system_branch=any(
            isinstance(x,dict) and participant_types.get(str(x.get('participant') or ''))=='system'
            for x in adjacent
        )
        if has_system_branch:
            pid=str(n.get('participant') or '')
            if participant_types.get(pid)!='system':
                errors.append(
                    f'{gid}: parallel gateway coordinates a system-executed branch and must reference a participant with type=system; '
                    f'do not place automatic split/join control in a human lane'
                )

    errors.extend(_validate_branch_exception_paths(tobe,analysis,active))

    # A deterministic Exclusive Gateway that becomes the executor of an explicitly
    # full-automated replacement must live in a system lane. This is deliberately
    # narrow: human judgment gateways are not systemized merely because automation
    # exists elsewhere in the improvement.
    change_by_id={c.get('improvement_id'):c for c in change if isinstance(c,dict)}
    for iid in active:
        imp=improvements.get(iid) or {}
        auto=imp.get('automation') or {}
        recs=set(str(x) for x in (imp.get('recommendations') or []))
        entry=change_by_id.get(iid) or {}
        if auto.get('level')!='full' or 'automate' not in recs:
            continue
        source_ids=[str(x) for x in (entry.get('source_node_ids') or [])]
        removed_human_tasks=[sid for sid in source_ids if isinstance(sm.get(sid),dict) and sm[sid].get('type')=='task' and sid not in tm]
        if not removed_human_tasks:
            continue
        for tid in entry.get('target_node_ids') or []:
            tgt=tm.get(str(tid))
            if not isinstance(tgt,dict) or tgt.get('type')!='gateway_exclusive':
                continue
            pid=str(tgt.get('participant') or '')
            if participant_types.get(pid)!='system':
                errors.append(
                    f'{iid}: automated replacement gateway {tid} must reference a participant with type=system; '
                    f'it replaces removed task(s) {removed_human_tasks} under automation.level=full'
                )
    def comparable_node(n):
        if not isinstance(n,dict): return n
        # duration/frequency are As-Is baseline measurements and are intentionally
        # not carried as To-Be actuals.
        return {k:v for k,v in n.items() if k not in {'duration','frequency'}}
    changed_nodes=[]
    for nid in set(sm)|set(tm):
        if nid not in sm or nid not in tm or comparable_node(sm[nid])!=comparable_node(tm[nid]):changed_nodes.append(nid)
    changed_edges=[]
    for eid in set(se)|set(te):
        if eid not in se or eid not in te or se[eid]!=te[eid]:changed_edges.append(eid)
    untracked_nodes=[x for x in changed_nodes if x not in covered_nodes]
    untracked_edges=[x for x in changed_edges if x not in covered_edges]
    if untracked_nodes:errors.append(f'changed nodes not covered by change_log: {sorted(untracked_nodes)}')
    if untracked_edges:errors.append(f'changed edges not covered by change_log: {sorted(untracked_edges)}')
    # As-Is issue history and To-Be issues have different semantics. Classify source issues
    # not only when a task structurally changed, but also when an active improvement targets it.
    # This prevents an As-Is metric/issue from surviving as a To-Be issue merely because the
    # node body itself did not otherwise change.
    active_target_nodes=set()
    for iid in active:
        imp=improvements.get(iid) or {}
        active_target_nodes.update(str(x) for x in (imp.get('target_tasks') or []) if str(x) in tm)
    disposition_nodes=set(changed_nodes) | active_target_nodes
    target_metric_entries={}
    for t in performance_targets:
        if not isinstance(t,dict): continue
        metric=t.get('metric')
        if not isinstance(metric,str) or not metric.strip(): continue
        for nid in (t.get('source_node_ids') or []) + (t.get('target_node_ids') or []):
            target_metric_entries.setdefault(str(nid),set()).add(metric.strip())

    for nid in sorted(disposition_nodes):
        src=sm.get(nid); tgt=tm.get(nid)
        if not isinstance(src,dict) or src.get('type')!='task' or not isinstance(tgt,dict) or tgt.get('type')!='task':
            continue
        src_issues=src.get('issues') or []
        if not isinstance(src_issues,list): src_issues=[]
        src_issues=[str(x) for x in src_issues if str(x).strip()]
        if not src_issues:
            continue
        entries=issue_disposition.get(str(nid))
        if not isinstance(entries,list):
            errors.append(f'{nid}: metadata.bpr.issue_disposition.{nid} must classify every As-Is issue because the task changed or is targeted by an active improvement')
            continue
        mapped={}
        tgt_issues=tgt.get('issues') or []
        if not isinstance(tgt_issues,list):
            errors.append(f'{nid}: To-Be issues must be a list'); tgt_issues=[]
        tgt_issues=[str(x) for x in tgt_issues]
        valid_metrics=target_metric_entries.get(str(nid),set())
        for ei,e in enumerate(entries,1):
            if not isinstance(e,dict):
                errors.append(f'{nid}: issue_disposition entry #{ei} must be an object'); continue
            source_issue=e.get('source_issue')
            if source_issue not in src_issues:
                errors.append(f'{nid}: issue_disposition entry #{ei} references unknown source_issue: {source_issue}')
                continue
            if source_issue in mapped:
                errors.append(f'{nid}: duplicate issue_disposition for source issue: {source_issue}')
            mapped[source_issue]=e
            status=e.get('status')
            if status not in {'resolved','remaining','changed'}:
                errors.append(f'{nid}: issue_disposition status must be resolved/remaining/changed')
            if not isinstance(e.get('note'),str) or not e.get('note','').strip():
                errors.append(f'{nid}: issue_disposition note is required for source issue: {source_issue}')
            if status=='resolved':
                if source_issue in tgt_issues:
                    errors.append(f'{nid}: resolved As-Is issue must not remain in To-Be issues: {source_issue}')
            elif status=='remaining':
                if source_issue not in tgt_issues:
                    errors.append(f'{nid}: remaining As-Is issue must remain in To-Be issues: {source_issue}')
            elif status=='changed':
                repl=e.get('to_be_issue')
                metric=e.get('performance_target_metric')
                has_repl=isinstance(repl,str) and bool(repl.strip())
                has_metric=isinstance(metric,str) and bool(metric.strip())
                if has_repl == has_metric:
                    errors.append(f'{nid}: changed issue must specify exactly one of to_be_issue or performance_target_metric for source issue: {source_issue}')
                if has_repl:
                    if repl not in tgt_issues:
                        errors.append(f'{nid}: changed issue to_be_issue must appear in To-Be issues: {repl}')
                if has_metric:
                    if metric.strip() not in valid_metrics:
                        errors.append(f'{nid}: performance_target_metric must reference a performance target linked to this node: {metric}')
                    if source_issue in tgt_issues:
                        errors.append(f'{nid}: As-Is issue moved to a performance target must not remain verbatim in To-Be issues: {source_issue}')
                if source_issue in tgt_issues and has_repl:
                    errors.append(f'{nid}: changed As-Is issue must not be copied verbatim into To-Be issues: {source_issue}')
        missing=[x for x in src_issues if x not in mapped]
        if missing:
            errors.append(f'{nid}: missing issue_disposition entries for As-Is issues: {missing}')

    # implementation_options are candidates, not automatically selected products.
    # Candidate-only products must not become fixed To-Be systems unless the user explicitly selected them in the decision record.
    src_text=_norm_semantic(json.dumps(source,ensure_ascii=False))
    for iid in active:
        imp=improvements.get(iid) or {}
        core={k:v for k,v in imp.items() if k not in {'implementation_options','source_refs'}}
        core_text=_norm_semantic(json.dumps(core,ensure_ascii=False))
        decision_entry=next((d for d in (decisions.get('decisions') or []) if isinstance(d,dict) and d.get('improvement_id')==iid),{})
        selected=set(decision_entry.get('selected_implementation_options') or [])
        for opt in imp.get('implementation_options') or []:
            if not isinstance(opt,dict): continue
            product=str(opt.get('product_or_service') or '').strip()
            if not product: continue
            pn=_norm_semantic(product)
            candidate_only=pn and pn not in src_text and pn not in core_text
            if not candidate_only or product in selected: continue
            for n in tobe.get('nodes') or []:
                if not isinstance(n,dict): continue
                system=str(n.get('system') or '')
                if pn in _norm_semantic(system):
                    errors.append(f'{iid}: implementation candidate {product} was fixed in To-Be node {n.get("id")} system without explicit Human Gate product selection')

    # Process-scope improvements must remain traceable to the surviving target tasks they affect.
    # change_by_id was built above for automated-gateway validation and is reused here.
    for iid in active:
        imp=improvements.get(iid) or {}
        entry=change_by_id.get(iid) or {}
        if imp.get('scope')!='process':
            continue
        expected_targets=[str(x) for x in (imp.get('target_tasks') or []) if str(x) in tm]
        actual_targets=set(str(x) for x in (entry.get('target_node_ids') or []))
        missing_targets=[x for x in expected_targets if x not in actual_targets]
        if missing_targets:
            errors.append(f'{iid}: process-scope change_log.target_node_ids must include surviving analysis target_tasks: {missing_targets}')

    # To-Be is a target design, not a post-implementation actual. Task-level
    # duration/frequency are therefore prohibited; keep As-Is actuals in
    # source_node_context and express future intent through performance_targets.
    for n in tobe.get('nodes') or []:
        if not isinstance(n,dict) or n.get('type')!='task':
            continue
        nid=str(n.get('id') or '')
        for field in ('duration','frequency'):
            if n.get(field) not in (None,''):
                errors.append(f'{nid}: To-Be task must not carry {field}; preserve As-Is baseline in source_node_context and use metadata.bpr.performance_targets')

    allowed_directions={'decrease','increase','maintain'}
    seen_targets=set()
    source_node_ids=set(sm)
    target_node_ids=set(tm)
    for i,t in enumerate(performance_targets,1):
        if not isinstance(t,dict):
            errors.append(f'performance_targets entry #{i} must be an object'); continue
        metric=t.get('metric')
        if not isinstance(metric,str) or not metric.strip():
            errors.append(f'performance_targets entry #{i}: metric is required')
            metric=f'#{i}'
        key=(metric.strip() if isinstance(metric,str) else str(metric), tuple(t.get('target_node_ids') or []))
        if key in seen_targets:
            errors.append(f'performance_targets entry #{i}: duplicate metric/target_node_ids combination: {key[0]}')
        seen_targets.add(key)
        if 'baseline' not in t:
            errors.append(f'performance_targets entry #{i}: baseline key is required (use null when unknown)')
        if 'target' not in t:
            errors.append(f'performance_targets entry #{i}: target key is required (use null when not yet set)')
        direction=t.get('direction')
        if direction not in allowed_directions:
            errors.append(f'performance_targets entry #{i}: direction must be decrease/increase/maintain')
        note=t.get('note')
        if not isinstance(note,str) or not note.strip():
            errors.append(f'performance_targets entry #{i}: note is required')
        rel=t.get('related_improvements') or []
        if not isinstance(rel,list) or not rel or not all(isinstance(x,str) for x in rel):
            errors.append(f'performance_targets entry #{i}: related_improvements must be a non-empty string list')
        else:
            unknown=[x for x in rel if x not in active]
            if unknown:
                errors.append(f'performance_targets entry #{i}: related_improvements must reference active improvements only: {unknown}')
        for field,valid_ids in (('source_node_ids',source_node_ids),('target_node_ids',target_node_ids)):
            vals=t.get(field) or []
            if not isinstance(vals,list) or not all(isinstance(x,str) for x in vals):
                errors.append(f'performance_targets entry #{i}: {field} must be a string list')
            else:
                unknown=[x for x in vals if x not in valid_ids]
                if unknown:
                    errors.append(f'performance_targets entry #{i}: unknown {field}: {unknown}')
        if t.get('target') is None and ('未設定' not in str(note) and '測定' not in str(note) and '未確定' not in str(note)):
            warnings.append(f'performance_targets entry #{i}: target is null; note should explain why the target value is not yet set')

    if active and not performance_targets:
        warnings.append('active improvements exist but metadata.bpr.performance_targets is empty')
    referenced_improvements=set()
    for t in performance_targets:
        if isinstance(t,dict):
            referenced_improvements.update(x for x in (t.get('related_improvements') or []) if isinstance(x,str))
    missing_target_links=[iid for iid in active if iid not in referenced_improvements]
    if missing_target_links:
        warnings.append(f'active improvements without an explicit performance target: {missing_target_links}')

    if not active:warnings.append('no approved/conditional improvements; To-Be generation is normally unnecessary')
    return errors,warnings,{'active_improvements':active,'conditional_improvements':[x['improvement_id'] for x in conditional],'changed_nodes':len(changed_nodes),'changed_edges':len(changed_edges),'issue_disposition_nodes':len(issue_disposition),'performance_targets':len(performance_targets),'open_question_disposition':len(open_question_disposition)}


def main():
    ap=argparse.ArgumentParser();sp=ap.add_subparsers(dest='cmd',required=True)
    w=sp.add_parser('write')
    for p in ('source-process','analysis','decisions','output'):w.add_argument('--'+p,required=True)
    w.add_argument('--json')
    v=sp.add_parser('validate')
    for p in ('source-process','analysis','decisions','input'):v.add_argument('--'+p,required=True)
    vd=sp.add_parser('validate-decisions')
    for p in ('source-process','analysis','decisions'):vd.add_argument('--'+p,required=True)
    args=ap.parse_args(); source=load_yaml(args.source_process);analysis=load_yaml(args.analysis);decisions=load_yaml(args.decisions)
    if args.cmd=='validate-decisions':
        errors,warnings,active,conditional=validate_decisions(decisions,analysis,source)
        result={'ok':not errors,'errors':errors,'warnings':warnings,'summary':{'active_improvements':active,'conditional_improvements':[x['improvement_id'] for x in conditional]}}
        print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(0 if not errors else 2)
    tobe=read_json(args) if args.cmd=='write' else load_yaml(args.input)
    if args.cmd=='write':
        tobe=enrich_tobe(tobe,source,analysis)
    errors,warnings,summary=validate_tobe(tobe,source,analysis,decisions)
    result={'ok':not errors,'errors':errors,'warnings':warnings,'summary':summary}
    if args.cmd=='write' and not errors:dump_yaml(tobe,args.output);result['output']=args.output
    print(json.dumps(result,ensure_ascii=False,indent=2));sys.exit(0 if not errors else 2)
if __name__=='__main__':main()
