"""Shared presentation functions for the Gap report; no network or browser scripts."""
import html, re
LABELS={'completed':'対話での整理が完了','in_progress':'対話で整理中','deferred':'次の確認へ持ち越し','decide':'決定','confirm':'確認','prepare':'準備','critical':'最優先','high':'優先','medium':'通常','low':'低め','blocked':'確認・準備が必要','ready':'着手可能','open':'未確認','resolved':'確認済み','unknown':'未確認','proposed':'候補・未確定','confirmed':'確定','analysis_complete':'分析の整理が完了','provisional':'暫定の分析','rules':'業務ルール','process':'業務の流れ','control':'管理・チェック','operations':'運用','technology':'システム','data':'データ','organization':'役割・責任','measurement':'効果の測定'}

def natural(value):
    text=str(value if value is not None else '未確認')
    text=re.sub(r'\*\*(.*?)\*\*',r'\1',text)
    text=re.sub(r'`([^`]+)`',r'\1',text)
    for a,b in [('execution_sequence','対話で整理した実行順'),('depends_on','前後関係'),('採用To-Be','採用された業務の設計'),('採用済みTo-Be','採用された業務の設計'),('SLA後','対応期限を過ぎた場合'),('readinessはblocked','業務開始には確認・準備が必要'),('原本パック','入力資料'),('file/field_path/original_text','資料名・記載位置・原文'),('mappings','業務の対応表'),('coverage','確認範囲'),('readiness','業務開始の準備状況')]: text=text.replace(a,b)
    for a,b in [('正本','分析データ'),('カバレッジ','確認した範囲'),('冪等性','繰り返し実行しても重複しない仕組み'),('冪等','重複防止'),('RACI','役割・責任の分担'),('SLA','対応期限・サービス基準'),('As-Is','現在の業務'),('To-Be','変更後の業務'),('approved','採用済み'),('applied','設計に反映済み'),('blocked','確認・準備が必要')]: text=text.replace(a,b)
    return text

def esc(value): return html.escape(natural(value),quote=True)
def label(value): return esc(LABELS.get(str(value),value))
def items(values):
    if not values: return '<p class="muted">記載なし</p>'
    if isinstance(values, str): values = [values]
    return '<ul>'+''.join('<li>'+esc(v)+'</li>' for v in values)+'</ul>'
def badge(value):
    tone={'critical':'red','high':'amber','resolved':'green','analysis_complete':'green','blocked':'amber'}.get(str(value),'gray')
    return '<span class="badge '+tone+'">'+label(value)+'</span>'
def links(values):
    return ' '.join('<a class="id" href="#'+html.escape(str(v),quote=True)+'">'+esc(v)+'</a>' for v in values) or 'なし'
def sources(refs):
    return items([str(r.get('file',''))+' / '+str(r.get('entity_id') or r.get('field') or '') for r in refs])
def table(headers,rows):
    return '<div class="table-wrap"><table><thead><tr>'+''.join('<th scope="col">'+esc(h)+'</th>' for h in headers)+'</tr></thead><tbody>'+''.join('<tr>'+''.join('<td>'+v+'</td>' for v in row)+'</tr>' for row in rows)+'</tbody></table></div>'

CSS='''
:root{color-scheme:light dark;--ink:CanvasText;--muted:color-mix(in srgb,CanvasText 70%,Canvas);--line:color-mix(in srgb,CanvasText 20%,Canvas);--teal:color-mix(in srgb,#0b9092 70%,CanvasText);--paper:Canvas;--surface:Canvas;--tint:color-mix(in srgb,CanvasText 4%,Canvas)}
*{box-sizing:border-box}html{scroll-behavior:smooth}body{margin:0;background:var(--paper);color:var(--ink);font:16px/1.7 "Yu Gothic UI","Meiryo",system-ui,sans-serif}main{max-width:1320px;margin:auto;padding:32px}
header{background:#123941;color:white;padding:36px;border-radius:18px}header p{color:#d4e7e8;margin:8px 0}h1{font-size:32px;line-height:1.35;margin:10px 0}h2{font-size:25px;margin:0 0 18px}h3{font-size:19px;line-height:1.55;margin:10px 0}h4{margin:14px 0 6px}p{margin:8px 0}a{color:var(--teal);text-underline-offset:3px}nav{display:flex;gap:10px;flex-wrap:wrap;padding:20px 0}nav a{padding:7px 14px;background:white;border:1px solid var(--line);border-radius:30px;text-decoration:none}
section{margin:24px 0;padding:28px;background:white;border:1px solid var(--line);border-radius:16px;scroll-margin-top:16px}.metrics,.cards,.steps{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:16px}.metric{padding:20px;border:1px solid var(--line);border-top:4px solid var(--teal);border-radius:12px}.number{display:block;font-size:34px;font-weight:750;line-height:1.2}.metric small,.muted{color:var(--muted)}.cards{grid-template-columns:repeat(3,minmax(0,1fr))}.card,.step{padding:20px;border:1px solid var(--line);border-radius:12px;overflow-wrap:anywhere}.card.critical{border-top:4px solid #b14538}.step{border-top:4px solid var(--teal)}.step .number{font-size:24px;color:var(--teal)}
.badge{display:inline-block;padding:3px 10px;border-radius:20px;font-size:13px;font-weight:700;white-space:normal}.red{background:#fbe8e5;color:#8a241b}.amber{background:#fff0d5;color:#795000}.green{background:#dcf2e8;color:#186047}.gray{background:#edf2f4;color:#435a68}.id{display:inline-block;font-size:13px;font-weight:700;font-family:ui-monospace,monospace;margin-right:5px}.callout{padding:18px 22px;border-left:4px solid #d39731;background:#fff8eb;margin:18px 0}.table-wrap{overflow-x:auto;border:1px solid var(--line);border-radius:10px}table{width:100%;border-collapse:collapse;table-layout:fixed;min-width:820px}th{background:#e8f1f2;text-align:left;color:#214b54}th,td{padding:14px;border-bottom:1px solid var(--line);vertical-align:top;overflow-wrap:anywhere}tr:nth-child(even){background:#f8fafb}th:first-child{width:18%}td p{margin:0 0 6px}ul{padding-left:22px;margin:8px 0}li{margin:6px 0}details{border-top:1px solid var(--line);padding:15px 0;scroll-margin-top:20px}summary{cursor:pointer;font-weight:700;list-style-position:inside}details[open] summary{margin-bottom:15px}.compare{display:grid;grid-template-columns:1fr 1fr;gap:14px}.compare>div{background:#f4f8f8;padding:18px;border-radius:10px}.compare strong{color:var(--teal)}.meta{font-size:13px;overflow-wrap:anywhere}footer{color:var(--muted);font-size:14px;padding:20px 0}
@media(max-width:900px){.metrics,.cards,.steps{grid-template-columns:repeat(2,minmax(0,1fr))}main{padding:18px}header,section{padding:22px}}
@media(max-width:560px){.cards,.steps,.compare{grid-template-columns:1fr}.metrics{gap:10px}.metric{padding:14px}h1{font-size:25px}h2{font-size:21px}main{padding:12px}header,section{padding:18px}table{min-width:760px}}
@media print{body{background:white;font-size:11px}main{max-width:none;padding:0}header{background:white;color:var(--ink);border-bottom:2px solid var(--teal);padding:12px}header p{color:var(--ink)}nav{display:none}section{border:0;padding:12px;margin:10px 0}.table-wrap{overflow:visible}table{min-width:0}h2,h3{break-after:avoid}.card,.step,tr{break-inside:avoid}.cards,.steps{grid-template-columns:repeat(2,1fr)}.badge{border:1px solid var(--line)}}
'''

# System colors also follow the inherited scheme in OneDrive's HTML viewer.
CSS+='''
.diagram{--dep-start:#cc803b;--dep-finalize:#aa78ce;--dep-execute:var(--teal);--dep-unknown:var(--muted)}.diagram .edge.relation-optional{stroke-dasharray:9 6;stroke-width:2}.diagram .edge.relation-unknown{stroke-dasharray:2 5;stroke-width:2}.diagram .edge.relation-required{stroke-width:2.5}.diagram .edge.gate-start{stroke:var(--dep-start)}.diagram .edge.gate-finalize{stroke:var(--dep-finalize)}.diagram .edge.gate-execute{stroke:var(--dep-execute)}.diagram .edge.gate-unknown{stroke:var(--dep-unknown)}.diagram .arrow.gate-start{fill:var(--dep-start)}.diagram .arrow.gate-finalize{fill:var(--dep-finalize)}.diagram .arrow.gate-execute{fill:var(--dep-execute)}.diagram .arrow.gate-unknown{fill:var(--dep-unknown)}.dependency-legend{padding:14px;border:1px solid var(--line);border-radius:10px}
html:has(#theme-light:checked){color-scheme:light}html:has(#theme-dark:checked){color-scheme:dark}.display-mode{display:flex;align-items:center;flex-wrap:wrap;gap:16px;border:1px solid var(--line);border-radius:12px;padding:12px 16px;margin:0 0 18px}.display-mode legend{font-weight:700}.display-mode label{cursor:pointer}.display-mode input{accent-color:var(--teal)}.display-mode small{color:var(--muted)}
nav a,section{background:var(--surface)}header{background:color-mix(in srgb,var(--teal) 18%,Canvas);color:var(--ink);border:1px solid var(--line)}header p{color:var(--muted)}th{background:color-mix(in srgb,var(--teal) 12%,Canvas);color:var(--ink)}tr:nth-child(even),.compare>div{background:var(--tint)}.callout{background:color-mix(in srgb,#d39731 12%,Canvas);color:var(--ink)}.red,.amber,.green,.gray{color:var(--ink)}.red{background:color-mix(in srgb,#ce6255 22%,Canvas)}.amber{background:color-mix(in srgb,#d39731 22%,Canvas)}.green{background:color-mix(in srgb,#209973 22%,Canvas)}.gray{background:var(--tint)}
.diagram{overflow:auto;border:1px solid var(--line);border-radius:12px;padding:12px;margin:20px 0}.diagram svg{display:block;max-width:none!important;width:auto;height:auto}.diagram text{fill:var(--ink);font-family:inherit}.diagram .node{fill:Canvas;stroke:var(--teal);stroke-width:1.5}.diagram .critical-node{fill:color-mix(in srgb,#ce6255 10%,Canvas)}.diagram .edge{stroke:var(--muted);fill:none;stroke-width:1.3}.diagram .arrow{fill:var(--muted)}.diagram .bar{fill:var(--teal)}.diagram .grid{stroke:var(--line)}.flow{display:flex;align-items:stretch;gap:12px;overflow:auto;margin:20px 0}.flow article{flex:1;min-width:190px;border:1px solid var(--line);border-top:4px solid var(--teal);border-radius:12px;padding:16px}.flow .next{align-self:center;color:var(--teal);font-size:28px}.flow small{display:block;color:var(--muted)}
@media print{:root{color-scheme:light!important}.display-mode{display:none}.diagram svg{max-width:100%!important;width:100%}.flow{overflow:visible}.flow article{min-width:0}.diagram{break-inside:avoid}}
'''

DIMENSIONS={'process':'業務プロセス','technology':'システム・機能','data':'データ','people':'人・スキル','organization':'役割・体制','rules':'ルール','control':'セキュリティ・管理','measurement':'効果の測定'}
CONTEXT_FIELDS={'impact':'誰に、どのような影響があるか','root_cause':'原因と、その確認状況','preserve':'維持すべき良い点','target_outcome':'実現したい業務の状態','response_strategy':'対応の方向・選択肢','scope':'今回の範囲・後続・対象外','success_measure':'到達条件・評価指標','priority_assessment':'重要度・緊急度・難易度・費用や資源','tradeoff':'後回し・対象外とした場合の影響'}

def identifier_guide(data):
    rows=[['GAP-','業務の変更点','現在の業務と変更後の業務の差分。何が不足し、何を変える必要があるかを整理します。'],['ACT-','必要な対応','Gapを埋めるために必要な対応の全体。ルール整備、設計、実装、検証などを含みます。'],['NA-','次の行動','対話で選んだ直近の一歩。照会、判断、準備など、いま何から始めるかを示します。'],['Q-','確認したい質問','回答や判断が必要な事項。確認済みになっても同じ番号で根拠を追跡します。']]
    out='<section id="identifier-guide"><h2>番号の読み方と、2つの図の違い</h2><p>番号は項目を参照するための目印です。数字の大小は優先度や実行順を表しません。</p>'+table(['番号の先頭','呼び方','表すこと'],[[esc(v) for v in row] for row in rows])
    out+='<p><strong>NAの図</strong>は直近の確認・判断・準備の前後関係、<strong>ACTの図</strong>はGapを埋めるための対応全体の前後関係を示します。NAとACTは1対1ではありません。1つのACTの一部をNAとして先行したり、1つのNAで複数のACTに必要な情報を集めたりします。<strong>NAを終えても、関連するACT全体が完了したことにはなりません。</strong></p>'
    for a in data.get('next_actions',[]):
        if a.get('related_action_ids'):
            out+='<p>このレポートの例：'+links([a['id']])+'「'+esc(a['title'])+'」は、'+links(a['related_action_ids'])+'を進めるための直近の一歩です。それぞれの対応の完了は、個別の完了条件で確認します。</p>'
            break
    return out+'</section>'

def gap_decision_context(gap):
    context=gap.get('decision_context') or {}
    return '<h4>変更を判断する材料</h4>'+table(['確認すること','整理した内容'],[[title,esc(context.get(key) or '資料・回答からは未確認。必要性を確認し、次の確認へつなげる。')] for key,title in CONTEXT_FIELDS.items()])+sources(context.get('source_refs',[]))

def analysis_context_section(data):
    scope=data.get('scope_summary') or {};dims=data.get('analysis_dimensions') or {}
    out=['<section id="analysis-context"><h2>変更を判断する材料と、今回の範囲</h2><p>資料にない情報は未確認として扱います。原因、費用、数値目標を推測で確定しません。維持する良い点も確認し、すべてを変更対象にはしません。</p>']
    out.append(table(['範囲','内容'],[[title,esc(scope.get(key) or '未確認・対話で整理')] for key,title in [('included','今回扱うこと'),('excluded','今回は扱わないこと'),('later','後続で扱うこと'),('external','他の取組との関係'),('temporary','暫定的な進め方')]]))
    rows=[]
    for key,title in DIMENSIONS.items():
        item=dims.get(key) or {}
        rows.append([title,esc(item.get('status') or '未確認'),esc(item.get('summary') or '資料の記載範囲と不足を確認する。該当しない場合も理由を残す。'),links(item.get('gap_ids',[]))+links(item.get('question_ids',[]))+sources(item.get('source_refs',[]))])
    out.append('<h3>分析で確認した観点</h3>'+table(['観点','確認状況','整理したこと・不足','関連項目・根拠'],rows))
    return ''.join(out)+'</section>'
