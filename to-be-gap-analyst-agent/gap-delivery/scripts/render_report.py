"""Create a standalone Japanese HTML report directly from analysis data."""
import argparse, html, json, re
from planning_report import dependency_layers, dependency_diagram, dependency_relations, validate_dependencies, dependency_summary, dependency_table
from business_calendar import schedule_diagram
from pathlib import Path

from report_format import *

GENERATOR_ID = "gap-delivery/render_report.py@2"

def validate_next_actions(data):
    rows=data.get('next_actions') or []; act_ids={a['id'] for a in data.get('actions',[])}; q_ids={q['id'] for q in data.get('questions',[])}
    ids=[a['id'] for a in rows]
    if len(ids)!=len(set(ids)): raise ValueError('Duplicate next action ID')
    by_id={a['id']:a for a in rows};visited=set();visiting=set()
    def visit(i):
        if i not in by_id: raise ValueError('Unknown next action dependency: '+i)
        if i in visiting: raise ValueError('Cyclic next action dependency: '+i)
        if i in visited:return
        visiting.add(i)
        for rel in dependency_relations(by_id[i]):
            if rel['type']=='required' and rel['gate']=='start':visit(rel['predecessor_id'])
        visiting.remove(i);visited.add(i)
    validate_dependencies(rows)
    for a in rows:
        if not a.get('first_step') or not a.get('expected_result'):raise ValueError('Next action needs first step and expected result: '+a['id'])
        if not set(a.get('related_action_ids',[])).issubset(act_ids):raise ValueError('Unknown related action: '+a['id'])
        if not set(a.get('question_ids',[])).issubset(q_ids):raise ValueError('Unknown related question: '+a['id'])
        if a.get('status')=='confirmed' and not a.get('source'):raise ValueError('Confirmed next action needs agreement source: '+a['id'])
        visit(a['id'])
    dialogue=data.get('dialogue') or {}
    if dialogue.get('status')=='completed' and (not dialogue.get('agreed_scope') or not dialogue.get('confirmation_source')):
        raise ValueError('Completed dialogue needs agreed scope and confirmation source')
    return rows

def next_action_section(data,rows):
    dialogue=data.get('dialogue') or {}
    out=['<section id="next-actions"><h2>次に行うこと</h2><p>NAは対話で選んだ直近の一歩です。ACTはGapを埋めるための対応全体で、NAを終えてもACT全体の完了にはなりません。<a href="#identifier-guide">番号と2つの図の説明</a>を確認できます。</p><p>最初の一歩、相談する相手、得たい結果を順に確認できます。行動内容への合意と、実際に作業を終えたことは分けて扱います。</p>']
    if not rows:out.append('<div class="callout">次の行動は、重要なGapと利用者の優先軸を確認して対話で整理します。</div>')
    else:
        next_graph=dependency_diagram(rows,esc,natural,label)
        for old,new in [('dep-title','next-dep-title'),('dep-desc','next-dep-desc'),('dep-arrow','next-dep-arrow'),('data-action','data-next-action'),('data-from','data-next-from'),('data-to','data-next-to')]:
            next_graph=next_graph.replace(old,new)
        next_graph=next_graph.replace('対応の依存関係','次の行動の前後関係').replace('矢印は先に完了が必要な対応から後続への関係です。','矢印は先に情報や準備が必要な行動から後続への関係です。')
        out.append('<h3>次の行動の前後関係</h3><p>着手前の必須条件と、確定・実施前までに必要な条件を区別します。任意の確認を後回しにする場合は、制約を確認してください。</p>'+next_graph)
        out.append(dependency_table(rows,esc,links,table))
        out.append(table(['次の行動・優先度','最初の一歩','相談する相手','得たい結果・関連する対応'],[[ '<strong id="'+esc(a['id'])+'">'+esc(a['id'])+' '+esc(a['title'])+'</strong><br>'+badge(a.get('priority','unknown'))+' '+('<span class="badge green">行動内容に合意</span>' if a.get('status')=='confirmed' else badge(a.get('status','proposed'))) +'<p>'+esc(a.get('reason'))+'</p>',esc(a['first_step']),esc(a.get('consult_with','候補を確認する'))+'<br>'+label(a.get('owner_status','unknown')),esc(a['expected_result'])+'<p>'+links(a.get('related_action_ids',[]))+'</p><p>関連する確認: '+links(a.get('question_ids',[]))+'</p><p>前後関係: '+dependency_summary(a,esc,links)+'</p>'] for a in rows]))
    out.append('<h3>対話で整理した内容</h3><p>整理の状態: '+badge(dialogue.get('status','in_progress'))+'</p><p><strong>今回の範囲</strong>: '+esc(dialogue.get('agreed_scope') or '対話で確認')+'</p><p>'+esc(dialogue.get('summary') or '優先度と次の行動を相談します。')+'</p>')
    out.append('<h3>次の確認へ持ち越したこと</h3>'+items(dialogue.get('deferred_topics',[])))
    if dialogue.get('confirmation_source'):out.append('<p class="muted">整理内容を確認した根拠: '+esc(dialogue['confirmation_source'])+'</p>')
    if isinstance(dialogue.get('final_confirmation'),dict):
        confirmation=dialogue['final_confirmation']
        out.append('<p class="muted">最終整理への了承を求めた質問: '+esc(confirmation.get('prompt',''))+'</p><p class="muted">その回答: '+esc(confirmation.get('response',''))+'</p>')
    return ''.join(out)+'</section>'

def render(data):
    next_actions=validate_next_actions(data); full_view=data.get('report_view')=='full'; detail_attr=' open' if full_view else ''
    gaps=data.get('gaps',[]);actions=data.get('actions',[]);questions=data.get('questions',[])
    validate_dependencies(actions)
    pending=[q for q in questions if q.get('status')!='resolved'];resolved=[q for q in questions if q.get('status')=='resolved']
    readiness=data.get('readiness',{});coverage=data.get('coverage',{})
    title=data.get('title') or data.get('process_name') or '業務改善に向けた差分と実施計画'
    out=['<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><meta name="generator" content="'+GENERATOR_ID+'"><title>'+esc(title)+'</title><style>'+CSS+'</style></head><body><main>']
    out.append('<fieldset class="display-mode"><legend>表示</legend><label><input id="theme-auto" type="radio" name="theme" checked> 自動</label><label><input id="theme-light" type="radio" name="theme"> 白い表示</label><label><input id="theme-dark" type="radio" name="theme"> 暗い表示</label><small>自動は閲覧環境の配色に合わせます。読みやすい表示を選べます。</small></fieldset>')
    out+=['<header><p>GAP ANALYSIS / 業務改善レポート</p><h1>'+esc(title)+'</h1><p>現在の業務と変更後の業務を比べ、必要な対応と確認事項を整理しました。</p><p class="meta">分析ID: '+esc(data.get('analysis_id'))+'　版: '+esc(data.get('analysis_version'))+'</p></header>']
    sections=[('overview','全体像'),('identifier-guide','番号の読み方'),('analysis-context','判断の材料と範囲'),('next-actions','次に行うこと'),('gaps','業務の変更点'),('actions','実施すること'),('questions','確認したいこと'),('roadmap','進める順序'),('evidence','資料と確認範囲')]
    out+=['<nav aria-label="レポート内の移動">'+''.join('<a href="#'+k+'">'+v+'</a>' for k,v in sections)+'</nav>']
    out+=['<section id="overview"><h2>Gapと次の行動の整理</h2><p>分析の状態: '+badge(data.get('status','unknown'))+'　対話の状態: '+badge((data.get('dialogue') or {}).get('status','in_progress'))+'</p><div class="callout"><strong>業務を変更する前に確認すること</strong><p>'+esc(readiness.get('reason','業務開始の準備状況は未確認です。'))+'</p><p>上記は業務を変更する前に確認する事項です。未確認事項は次の行動へつなげ、今回の整理内容に合意すればGapと行動の整理を完了できます。</p></div><div class="metrics">']
    for n,t,sub in [(len(gaps),'業務の変更点','実現に必要な差分'),(len(actions),'実施すること','担当と着手条件を確認'),(len(pending),'未確認の質問','回答や判断が必要'),(len(resolved),'確認済みの質問','根拠のある回答を反映')]: out+=['<div class="metric"><span class="number">'+str(n)+'</span><strong>'+t+'</strong><br><small>'+sub+'</small></div>']
    out+=['</div><h3>優先して確認する変更点</h3><div class="cards">']
    for g in [g for g in gaps if g.get('priority')=='critical']:
        out+=['<article class="card critical">'+badge(g.get('priority'))+'<h3><a href="#'+esc(g['id'])+'">'+esc(g['title'])+'</a></h3><p>'+esc(g.get('delta'))+'</p><p class="muted">'+esc(g['id'])+'</p></article>']
    out.append('</div></section>');out.append(identifier_guide(data));out.append(analysis_context_section(data));out.append(next_action_section(data,next_actions))
    out+=['<section id="gaps"><h2>現在から、どのように変わるか</h2><p class="muted">全体を比較したあと、各項目を開くと必要な対応・確認方法・根拠を読めます。</p>']
    out+=[table(['変更点・優先度','現在の業務','変更後の業務','必要な対応'],[[links([g['id']])+'<p><strong>'+esc(g['title'])+'</strong></p>'+badge(g.get('priority')),esc(g.get('as_is')),esc(g.get('to_be')),esc(g.get('delta'))] for g in gaps])]
    for g in gaps:
        out+=['<details'+detail_attr+' id="'+esc(g['id'])+'"><summary>'+esc(g['id'])+'　'+esc(g['title'])+'</summary><div class="compare"><div><strong>現在の業務</strong><p>'+esc(g.get('as_is'))+'</p></div><div><strong>変更後の業務</strong><p>'+esc(g.get('to_be'))+'</p></div></div><h4>必要な対応</h4><p>'+esc(g.get('delta'))+'</p><h4>優先度の理由</h4><p>'+esc(g.get('priority_reason'))+'</p>'+gap_decision_context(g)+'<h4>完了を確認する条件</h4>'+items(g.get('acceptance_criteria',[]))+'<p>関連する対応: '+links(g.get('action_ids',[]))+'</p><p>関連する質問: '+links(g.get('question_ids',[]))+'</p><h4>根拠資料</h4>'+sources(g.get('source_refs',[]))+'</details>']
    out+=['</section><section id="actions"><h2>実施することと、着手条件</h2><p>ACTはGapを埋めるために必要な対応の全体です。直近の一歩であるNAとの関連は「次に行うこと」の表で確認できます。</p>']
    out+=[table(['対応・優先度','担当候補と状態','前後関係・必要な段階','作成・確認するもの'],[[links([a['id']])+'<p><strong>'+esc(a['title'])+'</strong></p>'+badge(a.get('priority')),esc(a.get('owner_candidate'))+'<p class="muted">'+label(a.get('owner_status','unknown'))+'</p>'+badge(a.get('start_status','unknown')),dependency_summary(a,esc,links),items(a.get('deliverables') if a.get('deliverables') is not None else a.get('deliverable'))] for a in actions])]
    for a in actions: out+=['<details'+detail_attr+' id="'+esc(a['id'])+'"><summary>'+esc(a['id'])+'　'+esc(a['title'])+'</summary><h4>着手するための条件</h4>'+items(a.get('entry_conditions',[]))+'<h4>完了を確認する条件</h4>'+items(a.get('acceptance_criteria',[]))+'<p>関連する変更点: '+links(a.get('gap_ids',[]))+'</p></details>']
    out+=['</section><section id="questions"><h2>回答・判断をお願いしたいこと</h2><p>質問をまとめても、元資料の各記載との対応は分析データに残しています。</p>']
    out+=[table(['質問・状態','確認したいこと','回答をお願いする役割','判断が必要な理由／確認済みの内容'],[[ '<span id="'+esc(q['id'])+'" class="id">'+esc(q['id'])+'</span><br>'+badge(q.get('status','open')),esc(q.get('question')),esc(q.get('respondent_candidate')),esc(q.get('resolution') if q.get('status')=='resolved' else q.get('impact'))] for q in questions])]
    out+=['</section><section id="roadmap"><h2>進める順序と日程</h2><p class="muted">優先度は重要さです。着手、確定、実施で必要な条件は異なります。下の段階図と実行順は検討の目安で、一律に前段階のすべての完了を待つ意味ではありません。</p><div class="flow" aria-label="段階の全体像">']
    phases=data.get('roadmap',[])
    for i,p in enumerate(phases,1):
        if i>1: out.append('<span class="next" aria-hidden="true">→</span>')
        out.append('<article><small>段階 '+str(i)+'</small><strong>'+esc(re.sub(r'^\d+[.．]\s*','',p.get('phase',p.get('title',''))))+'</strong><p>'+links(p.get('action_ids',[]))+'</p></article>')
    out+=['</div><p class="muted">上図は全体像です。各段階で先に進められる範囲と必須条件は、次の図と表で確認してください。同じ担当が重なる場合は調整が必要です。</p><details'+detail_attr+'><summary>すべての対応の依存関係を図で見る</summary><p>この図はACTの対応全体の前後関係です。NAの図が示す直近の一歩よりも広い範囲を扱います。<a href="#identifier-guide">番号と2つの図の説明</a>も確認してください。</p>'+dependency_diagram(actions,esc,natural,label)+dependency_table(actions,esc,links,table)+'</details>']
    out.append('<h3>作業ごとの見積</h3>'+table(['対応','所要日数（営業日）','見積の根拠'],[[links([a['id']]),esc(a.get('duration_business_days') if a.get('duration_business_days') is not None else '未定'),esc(a.get('estimate_source') or '見積・回答を確認してから設定')] for a in actions]))
    out.append(schedule_diagram(data,actions,esc,label,links,table))
    sequence=data.get('execution_sequence') or []
    if sequence: out.append('<h3>対話で整理した実行順</h3>'+table(['順序','作業のまとまり','対応','理由・着手条件'],[[esc(p.get('order')),esc(p.get('name'))+'<br>'+badge(p.get('status','proposed')),links(p.get('action_ids',[])),esc(p.get('reason'))] for p in sequence]))
    plan=data.get('planning_decisions') or []
    if plan: out.append('<h3>対話で確認した計画の条件</h3>'+table(['確認したこと','回答・方針','確定状況','根拠'],[[esc(p.get('topic')),esc(p.get('decision')),label(p.get('status','proposed')),esc(p.get('source','未確認'))] for p in plan]))
    out.append('<h3>段階ごとの着手・完了条件</h3><div class="steps">')
    for i,p in enumerate(data.get('roadmap',[]),1): out+=['<article class="step"><span class="number">段階 '+str(i)+'</span><h3>'+esc(re.sub(r'^\d+[.．]\s*','',p.get('phase',p.get('title',''))))+'</h3><h4>始める条件</h4>'+items(p.get('start_condition', p.get('entry_conditions', [])))+'<h4>次へ進む条件</h4>'+items(p.get('transition_condition', p.get('exit_conditions', [])))+'<p>'+links(p.get('action_ids',[]))+'</p></article>']
    out+=['</div></section><section id="evidence"><h2>使用した資料と、確認した範囲</h2>']
    out+=[table(['資料','版','読み取った範囲'],[[esc(s.get('file')),esc(s.get('version',s.get('process_version',s.get('analysis_version','記載なし')))),esc(s.get('read_range',s.get('read_status','未確認')))] for s in data.get('source_manifest',[])])]
    out+=['<h3>分析で確認したこと</h3>'+items(data.get('verification',{}).get('performed',[]))+'<h3>まだ実施していない確認</h3>'+items(data.get('verification',{}).get('not_performed',[]))+'<h3>利用上の留意点</h3>'+items(data.get('verification',{}).get('limitations',[]))+'</section><footer>必要な判断と実施内容を検討するための資料です。担当者の確定や業務開始の承認は、関係者で確認してください。</footer></main></body></html>']
    return ''.join(out)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--analysis',required=True);p.add_argument('--output',required=True);p.add_argument('--title');a=p.parse_args()
    data=json.loads(Path(a.analysis).read_text(encoding='utf-8-sig'))
    if a.title: data['title']=a.title
    Path(a.output).write_text(render(data),encoding='utf-8')
