#!/usr/bin/env python3
import argparse, html, json
import yaml

LABELS={
'eliminate':'廃止','simplify':'簡素化','consolidate':'統合','standardize':'標準化','relocate':'移管','automate':'自動化','assist':'AI・ツール支援','retain':'維持',
'high':'高','medium':'中','low':'低','full':'完全自動化','partial':'部分自動化','assist_level':'支援',
'primary':'推奨候補','complementary':'補完候補','alternative':'代替候補','requires':'必須','any_of':'いずれか必要','enhances':'組み合わせで効果向上',
'loop':'ループ・手戻り','handoff':'担当間ハンドオフ','duplicate_entry':'重複入力','parallel_dependency':'並行処理・完了待ち'
}


def load(path):
    with open(path,encoding='utf-8') as f:return yaml.safe_load(f)
def esc(x): return html.escape(str(x or ''))
def ul(items, cls='plain-list'):
    items=items or []
    if not items:return '<span class="muted">なし</span>'
    return f'<ul class="{cls}">' + ''.join(f'<li>{esc(x)}</li>' for x in items) + '</ul>'
def badge(x, kind=''):
    return f'<span class="badge {kind}">{esc(LABELS.get(x,x))}</span>'
def q(v): return LABELS.get(v,v or '未設定')

def product_name(x):
    return str(x or '')

FIT_ORDER={'primary':0,'complementary':1,'alternative':2}
CONF_ORDER={'high':0,'medium':1,'low':2}

def sorted_options(options):
    indexed=list(enumerate(options or []))
    indexed.sort(key=lambda pair:(
        FIT_ORDER.get((pair[1] or {}).get('fit'),99),
        CONF_ORDER.get((pair[1] or {}).get('confidence'),99),
        pair[0]
    ))
    return [opt for _,opt in indexed]

def display_fit_label(fit, has_primary):
    if fit=='primary': return '推奨候補'
    if fit=='complementary': return '補完候補'
    if fit=='alternative': return '代替候補' if has_primary else '検討候補'
    return str(fit or '候補')

def fit_badge(fit, has_primary):
    kind='fit fit-primary' if fit=='primary' else ('fit fit-complementary' if fit=='complementary' else 'fit fit-alternative')
    return f'<span class="badge {kind}">{esc(display_fit_label(fit,has_primary))}</span>'



def render_html(process, analysis):
    p=process.get('process') or {}; imps=analysis.get('improvements') or []; analysis_id=analysis.get('analysis_id') or '未設定'
    task_name={n.get('id'):n.get('name') for n in process.get('nodes') or [] if isinstance(n,dict) and n.get('type')=='task'}
    summary=analysis.get('summary') or {}
    source_by_id={s.get('id'):s for s in analysis.get('research_sources') or [] if isinstance(s,dict)}
    pattern_cov=analysis.get('process_pattern_coverage') or []

    pattern_cards=[]
    for c in pattern_cov:
        if not isinstance(c,dict): continue
        pattern=c.get('pattern'); present=c.get('present') is True
        related=' / '.join(task_name.get(t,t) for t in c.get('related_tasks') or []) or 'なし'
        imp_ids=' / '.join(c.get('improvement_ids') or []) or 'なし'
        pattern_cards.append(f'''<div class="pattern-card"><div class="pattern-head"><strong>{esc(LABELS.get(pattern,pattern))}</strong><span class="badge">{'あり' if present else '該当なし'}</span></div><div><b>関連Task:</b> {esc(related)}</div><div><b>関連改善:</b> {esc(imp_ids)}</div><p>{esc(c.get('note'))}</p></div>''')
    pattern_html='<section class="pattern-review"><h2>プロセス横断評価</h2><p class="muted">改善案数とは独立して、ループ・ハンドオフ・重複入力・並行依存を確認した結果です。</p><div class="pattern-grid">'+''.join(pattern_cards)+'</div></section>' if pattern_cards else ''

    def source_links(refs):
        refs=refs or []
        if not refs:return '<span class="muted">なし</span>'
        out=[]
        for ref in refs:
            s=source_by_id.get(ref) or {}
            title=s.get('title') or ref; url=s.get('url') or ''
            if url: out.append(f'<a class="external-link" href="{esc(url)}" target="_blank" rel="noopener noreferrer" data-external-url="{esc(url)}">{esc(title)} <span aria-hidden="true">↗</span></a> <span class="source-id">({esc(ref)})</span>')
            else: out.append(f'{esc(title)} <span class="source-id">({esc(ref)})</span>')
        return '<br>'.join(out)

    cards=[]
    for imp in imps:
        iid=imp.get('id'); recs=imp.get('recommendations') or []; pr=imp.get('priority') or {}; eff=imp.get('expected_effect') or {}; auto=imp.get('automation') or {}
        targets=' / '.join(task_name.get(t,t) for t in imp.get('target_tasks') or []) or 'プロセス全体'
        ev=[]
        for e in imp.get('as_is_evidence') or []:
            ev.append(f"{task_name.get(e.get('task_id'),e.get('task_id'))}: {e.get('note','')}")
        auto_html='<span class="muted">評価なし</span>'
        if auto:
            cand=auto.get('candidate')
            cand_txt='候補あり' if cand is True else '候補なし' if cand is False else '未確定'
            lvl=auto.get('level')
            auto_html=f'<strong>{cand_txt}</strong>' + (f' / {esc(LABELS.get(lvl, lvl))}' if lvl else '') + (f'<p>{esc(auto.get("notes"))}</p>' if auto.get('notes') else '')

        dep_html='<span class="muted">なし</span>'
        deps=imp.get('dependencies') or []
        if deps:
            dep_items=[]
            for d in deps:
                ids=' / '.join(d.get('improvement_ids') or [])
                dep_items.append(f'<li><b>{esc(q(d.get("type")))}</b>: {esc(ids)}<br><span class="muted">{esc(d.get("note"))}</span></li>')
            dep_html='<ul class="plain-list">'+''.join(dep_items)+'</ul>'

        opts=sorted_options(imp.get('implementation_options') or [])
        no_opt_reason=imp.get('implementation_options_reason') or '現時点では具体的な機能・サービスを特定できる根拠が不足しています。'
        opt_html=f'<div class="no-option"><strong>具体候補なし</strong><p><b>理由:</b> {esc(no_opt_reason)}</p></div>'
        if opts:
            option_cards=[]
            has_primary=any((opt or {}).get('fit')=='primary' for opt in opts)
            for opt in opts:
                option_cards.append(f'''<div class="implementation-option">
  <div class="implementation-head"><strong>{esc(product_name(opt.get('product_or_service')))}</strong>{fit_badge(opt.get('fit'),has_primary)}</div>
  <div class="capability">{esc(opt.get('capability'))}</div>
  <p>{esc(opt.get('role'))}</p>
  <div class="option-meta">確度: <b>{esc(q(opt.get('confidence')))}</b></div>
  <div class="option-sub"><b>前提</b>{ul(opt.get('prerequisites'))}</div>
  <div class="option-sub"><b>根拠</b><div>{source_links(opt.get('source_refs'))}</div></div>
</div>''')
            opt_html='<div class="implementation-grid">'+''.join(option_cards)+'</div>'

        cards.append(f'''
<article class="proposal" id="{esc(iid)}" data-decision="undecided">
  <div class="proposal-head"><div><div class="id-row"><span class="proposal-id">{esc(iid)}</span><span class="decision-state" aria-live="polite">要判断</span></div><h2>{esc(imp.get('title'))}</h2></div>
  <div class="decision-box"><label for="decision-{esc(iid)}">判断</label><select id="decision-{esc(iid)}" class="decision" data-id="{esc(iid)}" aria-label="{esc(iid)} の判断"><option value="undecided">未判断（要判断）</option><option value="approved">採用</option><option value="conditional_approved">条件付き採用</option><option value="hold">保留</option><option value="rejected">見送り</option></select>
  <details class="decision-note-wrap"><summary>判断メモ（任意）</summary><div class="decision-note-hint" hidden>条件付き採用には採用条件の入力が必要です。</div><textarea class="decision-note" data-id="{esc(iid)}" rows="2" placeholder="判断理由などを必要に応じて記入してください"></textarea></details></div></div>
  <div class="meta"><span>対象: {esc(targets)}</span><span>スコープ: {'Task' if imp.get('scope')=='task' else 'プロセス横断'}</span></div>
  <div class="badges">{''.join(badge(r,'rec') for r in recs)}</div>
  <div class="grid4">
    <div><b>効果</b><span>{esc(q(eff.get('impact')))}</span></div><div><b>実装工数</b><span>{esc(q(pr.get('effort')))}</span></div><div><b>リスク</b><span>{esc(q(pr.get('risk')))}</span></div><div><b>確度</b><span>{esc(q(pr.get('confidence')))}</span></div>
  </div>
  <section><h3>提案内容</h3><p>{esc(imp.get('proposed_change'))}</p></section>
  <section><h3>提案理由</h3><p>{esc(imp.get('rationale'))}</p></section>
  <section><h3>期待効果</h3><p>{esc(eff.get('notes') or '未記載')}</p></section>
  <section><h3>自動化・支援評価</h3>{auto_html}</section>
  <section><h3>想定・推奨する機能 / サービス</h3>{opt_html}</section>
  <section><h3>関連・依存する改善案</h3>{dep_html}</section>
  <div class="twocol"><section><h3>前提条件</h3>{ul(imp.get('prerequisites'))}</section><section><h3>未確認事項</h3>{ul(imp.get('unresolved_questions'))}</section></div>
  <section><h3>As-Is上の根拠</h3>{ul(ev)}</section>
  <section><h3>外部根拠</h3><div>{source_links(imp.get('source_refs'))}</div></section>
</article>''')

    sources=[]
    for s in analysis.get('research_sources') or []:
        url=s.get('url') or ''
        link=f'<a class="external-link" href="{esc(url)}" target="_blank" rel="noopener noreferrer" data-external-url="{esc(url)}">{esc(s.get("title"))} <span aria-hidden="true">↗</span></a>' if url else esc(s.get('title'))
        sources.append(f'<li><b>{esc(s.get("id"))}</b> {link}<br><span class="muted">{esc(s.get("publisher"))} — {esc(s.get("note"))}</span></li>')
    openq=analysis.get('analysis_open_questions') or []
    data=json.dumps([{'id':x.get('id'),'title':x.get('title')} for x in imps],ensure_ascii=False).replace('</','<\\/')
    return f'''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>BPR改善分析 - {esc(p.get('name'))}</title>
<style>
:root{{--undecided:#b7791f;--approved:#2f855a;--conditional:#2b6cb0;--hold:#805ad5;--rejected:#718096;font-family:"Segoe UI","Yu Gothic UI",sans-serif;color-scheme:light dark}}*{{box-sizing:border-box}}body{{margin:0;background:Canvas;color:CanvasText}}header{{padding:28px 32px;border-bottom:1px solid color-mix(in srgb,CanvasText 18%,transparent)}}header h1{{margin:0 0 8px;font-size:28px}}header p{{margin:0;opacity:.78;line-height:1.6}}main{{max-width:1280px;margin:auto;padding:24px}}.notice{{border:1px solid color-mix(in srgb,var(--undecided) 58%,CanvasText 20%);border-radius:12px;padding:16px 18px;margin-bottom:20px;background:color-mix(in srgb,Canvas 94%,var(--undecided) 6%);line-height:1.65}}.summary{{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:12px;margin:18px 0}}.summary div{{border:1px solid color-mix(in srgb,CanvasText 16%,transparent);border-radius:12px;padding:16px}}.summary b{{display:block;font-size:28px}}.actions{{position:sticky;top:0;z-index:10;display:flex;gap:10px;align-items:center;flex-wrap:wrap;padding:12px;margin:0 0 18px;border:1px solid color-mix(in srgb,CanvasText 18%,transparent);border-radius:10px;background:color-mix(in srgb,Canvas 94%,transparent);backdrop-filter:blur(8px)}}button,.decision,textarea{{font:inherit;padding:8px 10px;border-radius:8px;border:1px solid color-mix(in srgb,CanvasText 26%,transparent);background:Canvas;color:CanvasText}}button{{cursor:pointer}}.progress{{font-weight:700;margin-left:auto}}.proposal{{border:1px solid color-mix(in srgb,CanvasText 18%,transparent);border-left-width:6px;border-radius:14px;padding:22px;margin:0 0 20px;transition:border-color .15s ease,background .15s ease}}.proposal[data-decision="undecided"]{{border-left-color:var(--undecided);background:color-mix(in srgb,Canvas 98%,var(--undecided) 2%)}}.proposal[data-decision="approved"]{{border-left-color:var(--approved);background:color-mix(in srgb,Canvas 98%,var(--approved) 2%)}}.proposal[data-decision="conditional_approved"]{{border-left-color:var(--conditional);background:color-mix(in srgb,Canvas 98%,var(--conditional) 2%)}}.proposal[data-decision="hold"]{{border-left-color:var(--hold);background:color-mix(in srgb,Canvas 98%,var(--hold) 2%)}}.proposal[data-decision="rejected"]{{border-left-color:var(--rejected);opacity:.82}}.proposal-head{{display:flex;justify-content:space-between;gap:20px;align-items:flex-start}}.proposal-head h2{{margin:4px 0 6px;font-size:22px}}.id-row{{display:flex;align-items:center;gap:9px}}.proposal-id{{font-weight:700;opacity:.7}}.decision-state{{font-size:13px;font-weight:700;padding:3px 8px;border-radius:999px;background:color-mix(in srgb,var(--undecided) 16%,transparent);color:CanvasText}}.proposal[data-decision="approved"] .decision-state{{background:color-mix(in srgb,var(--approved) 18%,transparent)}}.proposal[data-decision="conditional_approved"] .decision-state{{background:color-mix(in srgb,var(--conditional) 18%,transparent)}}.proposal[data-decision="hold"] .decision-state{{background:color-mix(in srgb,var(--hold) 18%,transparent)}}.proposal[data-decision="rejected"] .decision-state{{background:color-mix(in srgb,var(--rejected) 18%,transparent)}}.decision-box{{min-width:210px}}.decision-box label{{display:block;font-size:13px;font-weight:700;margin-bottom:4px}}.decision{{width:100%}}.decision-note-wrap{{margin-top:8px;font-size:13px}}.decision-note-wrap summary{{cursor:pointer;opacity:.78}}.decision-note-hint{{margin-top:8px;padding:7px 9px;border-radius:7px;background:color-mix(in srgb,var(--conditional) 10%,transparent);font-weight:700;line-height:1.45}}.decision-note{{width:100%;margin-top:7px;resize:vertical;min-height:58px;font-size:14px}}.decision-note.required{{border:2px solid color-mix(in srgb,var(--conditional) 72%,CanvasText 20%)}}.meta{{display:flex;gap:18px;flex-wrap:wrap;opacity:.78;margin-bottom:10px}}.badge{{display:inline-block;padding:4px 9px;border-radius:999px;margin:0 6px 6px 0;background:color-mix(in srgb,CanvasText 10%,transparent)}}.fit{{font-size:12px;margin:0;border:1px solid transparent}}.fit-primary{{font-weight:700;background:color-mix(in srgb,var(--conditional) 16%,transparent);border-color:color-mix(in srgb,var(--conditional) 34%,transparent)}}.fit-complementary{{background:color-mix(in srgb,var(--approved) 10%,transparent);border-color:color-mix(in srgb,var(--approved) 22%,transparent)}}.fit-alternative{{background:color-mix(in srgb,CanvasText 8%,transparent)}}.grid4{{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:8px;margin:14px 0}}.grid4 div{{padding:12px;border-radius:10px;background:color-mix(in srgb,CanvasText 7%,transparent)}}.grid4 b,.grid4 span{{display:block}}.grid4 span{{font-size:18px;margin-top:4px}}section h3{{font-size:15px;margin:16px 0 6px;opacity:.72}}section p{{white-space:pre-wrap;line-height:1.65;margin:0}}.twocol{{display:grid;grid-template-columns:1fr 1fr;gap:18px}}.implementation-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}.implementation-option{{border:1px solid color-mix(in srgb,CanvasText 14%,transparent);border-radius:10px;padding:13px}}.implementation-head{{display:flex;justify-content:space-between;gap:8px;align-items:flex-start}}.no-option{{border-left:4px solid color-mix(in srgb,CanvasText 24%,transparent);padding:8px 12px;background:color-mix(in srgb,CanvasText 4%,transparent);border-radius:8px}}.no-option p{{margin-top:6px}}.pattern-review{{margin:20px 0}}.pattern-grid{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}}.pattern-card{{border:1px solid color-mix(in srgb,CanvasText 14%,transparent);border-radius:10px;padding:13px}}.pattern-card p{{margin:.5em 0 0;line-height:1.55}}.pattern-head{{display:flex;justify-content:space-between;gap:8px;align-items:center;margin-bottom:8px}}.capability{{font-weight:600;margin-top:4px}}.option-meta{{font-size:14px;margin-top:8px}}.option-sub{{font-size:14px;margin-top:8px}}ul{{margin:.4em 0;padding-left:1.4em}}li{{margin:.35em 0;line-height:1.55}}.muted{{opacity:.66}}.source-id{{font-size:12px;opacity:.65}}.sources,.openq{{border-top:1px solid color-mix(in srgb,CanvasText 16%,transparent);padding-top:18px;margin-top:28px}}#copy-status{{font-size:14px;opacity:.8}}#decision-output-wrap{{display:none;width:100%;padding-top:8px}}#decision-output-wrap.visible{{display:block}}#decision-output{{width:100%;min-height:150px;resize:vertical}}.external-link{{text-decoration:underline;text-underline-offset:2px}}#external-link-status{{display:none;width:100%;padding:9px 11px;border-radius:8px;background:color-mix(in srgb,var(--conditional) 9%,Canvas);line-height:1.45}}#external-link-status.visible{{display:block}}@media(max-width:800px){{.summary{{grid-template-columns:1fr 1fr}}.grid4,.twocol,.implementation-grid,.pattern-grid{{grid-template-columns:1fr 1fr}}.proposal-head{{display:block}}.decision-box{{margin-top:10px;min-width:0}}.progress{{margin-left:0}}}}@media(max-width:520px){{.summary,.grid4,.twocol,.implementation-grid,.pattern-grid{{grid-template-columns:1fr}}}}
</style></head><body>
<header><h1>BPR改善分析レポート</h1><p>{esc(p.get('name'))} / As-Is {esc(p.get('version'))} を基準にした改善提案です。これはTo-Be確定版ではありません。採用する改善案を人が判断した後にTo-Beを生成します。</p><p><b>分析ID:</b> <code>{esc(analysis_id)}</code></p></header>
<main>
<div class="notice"><b>Human Gate</b><br><b>未判断は「人による判断がまだ必要」な状態です。</b> 各提案を「採用 / 条件付き採用 / 保留 / 見送り」で判断してください。条件付き採用では採用条件の入力が必須です。To-Beには採用・条件付き採用だけを反映します。</div>
<div class="summary"><div><span>改善案</span><b>{summary.get('improvement_count',len(imps))}</b></div><div><span>Task単位</span><b>{summary.get('task_scope_count',0)}</b></div><div><span>プロセス横断</span><b>{summary.get('process_scope_count',0)}</b></div><div><span>高インパクト</span><b>{summary.get('high_impact_count',0)}</b></div><div><span>実装候補</span><b>{summary.get('implementation_option_count',0)}</b></div></div>
{pattern_html}
<div class="actions"><button id="copy" type="button">判断結果をコピー</button><button id="clear" type="button">判断をリセット</button><span id="copy-status" role="status" aria-live="polite"></span><span id="decision-progress" class="progress"></span><div id="external-link-status" role="status" aria-live="polite"></div><div id="decision-output-wrap"><label for="decision-output"><b>判断結果</b>（自動コピーできない場合はここからコピーしてください）</label><textarea id="decision-output" readonly></textarea></div></div>
{''.join(cards)}
<section class="openq"><h2>分析全体の未確認事項</h2>{ul(openq)}</section>
<section class="sources"><h2>調査ソース</h2><ul>{''.join(sources) if sources else '<li class="muted">外部ソースなし</li>'}</ul></section>
</main>
<script type="application/json" id="proposal-data">{data}</script>
<script>
(()=>{{
const proposals=JSON.parse(document.getElementById('proposal-data').textContent);
const labels={{approved:'採用',conditional_approved:'条件付き採用',hold:'保留',rejected:'見送り',undecided:'未判断'}};
const states={{approved:'採用',conditional_approved:'条件付き',hold:'保留',rejected:'見送り',undecided:'要判断'}};
const status=document.getElementById('copy-status');
const outputWrap=document.getElementById('decision-output-wrap');
const output=document.getElementById('decision-output');
const progress=document.getElementById('decision-progress');
const externalLinkStatus=document.getElementById('external-link-status');
function decisionFor(id){{
  const select=document.querySelector(`select[data-id="${{id}}"]`);
  const note=document.querySelector(`textarea.decision-note[data-id="${{id}}"]`);
  return {{value:select?.value||'undecided',note:(note?.value||'').trim()}};
}}
const analysisId='{esc(analysis_id)}';
function lines(){{return `分析ID: ${{analysisId}}\n`+proposals.map(p=>{{const d=decisionFor(p.id);const suffix=d.note?` | メモ: ${{d.note}}`:'';return `${{p.id}}: ${{labels[d.value]}}${{suffix}} - ${{p.title}}`;}}).join('\\n');}}
function updateDecisionState(card,value,noteValue){{
  const pill=card.querySelector('.decision-state');
  if(!pill)return;
  if(value==='conditional_approved'&&!String(noteValue||'').trim())pill.textContent='条件入力待ち';
  else pill.textContent=states[value]||value;
}}
function updateCard(select){{
  const id=select.dataset.id; const card=document.getElementById(id); if(!card)return;
  const value=select.value; card.dataset.decision=value;
  const details=card.querySelector('.decision-note-wrap'); const note=card.querySelector('.decision-note'); const hint=card.querySelector('.decision-note-hint'); const summaryEl=details?.querySelector('summary');
  if(value==='conditional_approved'){{
    if(details)details.open=true;
    if(summaryEl)summaryEl.textContent='採用条件（必須）';
    if(hint)hint.hidden=false;
    if(note){{note.classList.add('required');note.setAttribute('aria-required','true');note.placeholder='この改善案を採用する条件を入力してください（必須）';}}
  }} else {{
    if(summaryEl)summaryEl.textContent='判断メモ（任意）';
    if(hint)hint.hidden=true;
    if(note){{note.classList.remove('required');note.removeAttribute('aria-required');note.placeholder='判断理由などを必要に応じて記入してください';}}
  }}
  updateDecisionState(card,value,note?.value||'');
  updateProgress();
}}
function updateProgress(){{
  const values=proposals.map(p=>decisionFor(p.id).value); const undecided=values.filter(v=>v==='undecided').length;
  progress.textContent=undecided?`要判断: ${{undecided}}件 / ${{proposals.length}}件`:`全${{proposals.length}}件を判断済み`;
}}
function validateConditional(){{
  const missing=[];
  proposals.forEach(p=>{{const d=decisionFor(p.id);if(d.value==='conditional_approved'&&!d.note)missing.push(p.id);}});
  if(missing.length){{
    status.textContent=`条件付き採用の条件が未入力です: ${{missing.join(', ')}}`;
    const card=document.getElementById(missing[0]);
    const details=card?.querySelector('.decision-note-wrap'); if(details)details.open=true;
    card?.scrollIntoView({{behavior:'smooth',block:'center'}});
    setTimeout(()=>card?.querySelector('.decision-note')?.focus(),220);
    return false;
  }}
  return true;
}}
async function tryClipboard(text){{
  if(navigator.clipboard&&window.isSecureContext){{try{{await navigator.clipboard.writeText(text);return true;}}catch(e){{}}}}
  const ta=document.createElement('textarea');ta.value=text;ta.setAttribute('readonly','');ta.style.position='absolute';ta.style.left='-9999px';document.body.appendChild(ta);ta.select();ta.setSelectionRange(0,ta.value.length);
  let ok=false;try{{ok=document.execCommand('copy');}}catch(e){{ok=false;}}document.body.removeChild(ta);return ok;
}}
document.querySelectorAll('.decision').forEach(s=>{{s.addEventListener('change',()=>{{updateCard(s);if(s.value==='conditional_approved')setTimeout(()=>document.querySelector(`textarea.decision-note[data-id="${{s.dataset.id}}"]`)?.focus(),0);}});updateCard(s);}});
document.querySelectorAll('.decision-note').forEach(note=>{{note.addEventListener('input',()=>{{const card=document.getElementById(note.dataset.id);const select=document.querySelector(`select.decision[data-id="${{note.dataset.id}}"]`);if(card&&select){{updateDecisionState(card,select.value,note.value);}}}});}});
document.querySelectorAll('a.external-link').forEach(a=>{{a.addEventListener('click',async(e)=>{{
  e.preventDefault();
  const url=a.dataset.externalUrl||a.href;
  let opened=null;
  try{{opened=window.open(url,'_blank');if(opened){{try{{opened.opener=null;}}catch(_e){{}}}}}}catch(_e){{opened=null;}}
  if(opened){{externalLinkStatus.classList.remove('visible');externalLinkStatus.textContent='';return;}}
  const copied=await tryClipboard(url);
  externalLinkStatus.textContent=copied?'この表示環境では新しいタブを開けませんでした。URLをクリップボードへコピーしました。':'この表示環境では新しいタブを開けませんでした。リンクを右クリックしてURLをコピーしてください。';
  externalLinkStatus.classList.add('visible');
}});}});
document.getElementById('copy').addEventListener('click',async()=>{{
  if(!validateConditional())return;
  const text=lines();output.value=text;
  const ok=await tryClipboard(text);
  if(ok){{status.textContent='判断結果をコピーしました';outputWrap.classList.remove('visible');}}
  else{{status.textContent='自動コピーできませんでした。下の判断結果を選択してコピーしてください。';outputWrap.classList.add('visible');output.focus();output.select();}}
}});
document.getElementById('clear').addEventListener('click',()=>{{document.querySelectorAll('.decision').forEach(s=>{{s.value='undecided';updateCard(s);}});document.querySelectorAll('.decision-note').forEach(x=>x.value='');status.textContent='';externalLinkStatus.textContent='';externalLinkStatus.classList.remove('visible');output.value='';outputWrap.classList.remove('visible');}});
updateProgress();
}})();
</script></body></html>'''


def render_md(process,analysis):
    p=process.get('process') or {}; imps=analysis.get('improvements') or []; analysis_id=analysis.get('analysis_id') or '未設定'
    task_name={n.get('id'):n.get('name') for n in process.get('nodes') or [] if isinstance(n,dict) and n.get('type')=='task'}
    source_by_id={s.get('id'):s for s in analysis.get('research_sources') or [] if isinstance(s,dict)}
    out=[f"# BPR改善分析レポート - {p.get('name','')}","",f"> 分析ID: `{analysis_id}`","","> このレポートは改善提案です。To-Be確定版ではありません。改善IDごとに採用・条件付き採用・保留・見送りを判断してください。",""]
    pattern_cov=analysis.get('process_pattern_coverage') or []
    if pattern_cov:
        out += ["## プロセス横断評価","","改善案数とは独立して、ループ・ハンドオフ・重複入力・並行依存を確認しています。",""]
        for c in pattern_cov:
            if not isinstance(c,dict): continue
            related=' / '.join(task_name.get(t,t) for t in c.get('related_tasks') or []) or 'なし'
            imp_ids=' / '.join(c.get('improvement_ids') or []) or 'なし'
            out += [f"### {LABELS.get(c.get('pattern'),c.get('pattern'))}: {'あり' if c.get('present') is True else '該当なし'}","",f"- 関連Task: {related}",f"- 関連改善: {imp_ids}",f"- 評価: {c.get('note','')}",""]
    for imp in imps:
        pr=imp.get('priority') or {}; eff=imp.get('expected_effect') or {}; targets=' / '.join(task_name.get(t,t) for t in imp.get('target_tasks') or []) or 'プロセス全体'
        out += [f"## {imp.get('id')} {imp.get('title')}","",f"- 対象: {targets}",f"- 分類: {', '.join(LABELS.get(r,r) for r in imp.get('recommendations') or [])}",f"- 効果: {q(eff.get('impact'))} / 実装工数: {q(pr.get('effort'))} / リスク: {q(pr.get('risk'))} / 確度: {q(pr.get('confidence'))}","",f"**提案内容**: {imp.get('proposed_change','')}","",f"**理由**: {imp.get('rationale','')}",""]
        opts=sorted_options(imp.get('implementation_options') or [])
        out += ["**想定・推奨する機能 / サービス**"]
        if opts:
            has_primary=any((opt or {}).get('fit')=='primary' for opt in opts)
            for opt in opts:
                refs=[]
                for ref in opt.get('source_refs') or []:
                    s=source_by_id.get(ref) or {}; refs.append(s.get('title') or ref)
                out.append(f"- {product_name(opt.get('product_or_service'))}: {opt.get('capability')} — {opt.get('role')}（{display_fit_label(opt.get('fit'),has_primary)} / 確度 {q(opt.get('confidence'))}）" + (f" [根拠: {', '.join(refs)}]" if refs else ""))
        else:
            out.append('- 具体候補なし')
            out.append(f"- 理由: {imp.get('implementation_options_reason') or '現時点では具体的な機能・サービスを特定できる根拠が不足しています。'}")
        out.append("")
        deps=imp.get('dependencies') or []
        if deps:
            out += ["**関連・依存する改善案**"]
            out += [f"- {q(d.get('type'))}: {', '.join(d.get('improvement_ids') or [])} — {d.get('note','')}" for d in deps]
            out.append("")
        if imp.get('unresolved_questions'): out += ["**未確認事項**",*['- '+x for x in imp.get('unresolved_questions')],""]
    out += ["## Human Gate","","BPR Agentへ次の形式で判断を伝えてください。条件付き採用では条件を必ず記入してください。","","```text",f"分析ID: {analysis_id}","IMP-001: 採用","IMP-002: 条件付き採用 | メモ: 業務責任者が再申請ルールを確定した場合","IMP-003: 保留","IMP-004: 見送り","```",""]
    return '\n'.join(out)


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--process',required=True);ap.add_argument('--analysis',required=True);ap.add_argument('--output-html',required=True);ap.add_argument('--output-md',required=True)
    args=ap.parse_args();process=load(args.process);analysis=load(args.analysis)
    with open(args.output_html,'w',encoding='utf-8',newline='\n') as f:f.write(render_html(process,analysis))
    with open(args.output_md,'w',encoding='utf-8',newline='\n') as f:f.write(render_md(process,analysis))
    print(json.dumps({'ok':True,'html':args.output_html,'markdown':args.output_md,'improvements':len(analysis.get('improvements') or [])},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
