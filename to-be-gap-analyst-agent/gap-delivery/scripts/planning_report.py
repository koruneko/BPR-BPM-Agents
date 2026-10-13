from datetime import date

RELATION_LABELS={'required':'必須','optional':'任意・先に行うと望ましい','unknown':'要確認'}
GATE_LABELS={'start':'着手前','finalize':'確定前','execute':'実施・移行前','unknown':'段階未確認'}

def dependency_relations(action):
    explicit=action.get('dependency_relations',[]); result=[]; seen=set()
    for rel in explicit:
        i=rel.get('predecessor_id'); kind=rel.get('type'); gate=rel.get('gate')
        if not i or i in seen:raise ValueError('Missing or duplicate predecessor: '+str(i))
        if kind not in RELATION_LABELS or gate not in GATE_LABELS:raise ValueError('Unknown dependency type or gate')
        if not rel.get('reason') or not rel.get('source'):raise ValueError('Dependency needs reason and source')
        if kind=='required' and (gate=='unknown' or not rel.get('condition')):raise ValueError('Required dependency needs gate and condition')
        if kind=='optional' and (not rel.get('if_deferred') or not rel.get('can_proceed')):raise ValueError('Optional dependency needs deferral constraints and allowed work')
        seen.add(i);result.append(rel)
    for i in action.get('depends_on',[]):
        if i not in seen:
            result.append({'predecessor_id':i,'type':'unknown','gate':'unknown','reason':'以前の分析に前後関係の記載がありますが、必須性と必要な段階は未確認です。','condition':'条件を確認する','can_proceed':'着手可否を確認する。実施可能とは断定しない。','if_deferred':'影響を確認してから進め方を判断する。','source':'以前の分析の前後関係'})
            seen.add(i)
    return result

def validate_dependencies(actions):
    by_id={a['id']:a for a in actions}
    if len(by_id)!=len(actions):raise ValueError('Duplicate action ID')
    for a in actions:
        for rel in dependency_relations(a):
            if rel['predecessor_id'] not in by_id:raise ValueError('Unknown dependency: '+rel['predecessor_id'])
            if rel['predecessor_id']==a['id']:raise ValueError('Self dependency: '+a['id'])
    done=set();visiting=set()
    def visit(i):
        if i in visiting:raise ValueError('Cyclic required start dependency: '+i)
        if i in done:return
        visiting.add(i)
        for rel in dependency_relations(by_id[i]):
            if rel['type']=='required' and rel['gate']=='start':visit(rel['predecessor_id'])
        visiting.remove(i);done.add(i)
    for i in by_id:visit(i)
    return by_id

def schedule_predecessors(action):
    result=[]
    for rel in dependency_relations(action):
        if rel['type']=='unknown':raise ValueError('日程作成前に前後関係の必須性を確認してください: '+action['id'])
        if rel['type']=='required':
            if rel['gate']!='start':raise ValueError('確定・実施前の条件は作業を段階に分けて日程へ反映してください: '+action['id'])
            if rel.get('status')!='confirmed':raise ValueError('日程作成前に必須条件への合意が必要です: '+action['id'])
            result.append(rel['predecessor_id'])
        elif rel.get('status')!='confirmed' or not rel.get('deferral_agreed'):
            raise ValueError('日程で任意の先行確認を外すには制約を説明して了承が必要です: '+action['id'])
    return result

def dependency_layers(actions):
    by_id=validate_dependencies(actions);ranks={};visiting=set()
    def rank(i):
        if i in visiting:return 0
        if i in ranks:return ranks[i]
        visiting.add(i)
        ranks[i]=max((rank(rel['predecessor_id'])+1 for rel in dependency_relations(by_id[i]) if rel['predecessor_id'] not in visiting),default=0)
        visiting.remove(i);return ranks[i]
    for i in by_id:rank(i)
    return [[a for a in actions if ranks[a['id']]==n] for n in range(max(ranks.values(),default=-1)+1)]

def dependency_summary(action,esc,links):
    rows=dependency_relations(action)
    return '<br>'.join(links([rel['predecessor_id']])+' '+esc(RELATION_LABELS[rel['type']])+' / '+esc(GATE_LABELS[rel['gate']]) for rel in rows) or '前後関係の記載なし。個別の着手条件を確認。'

def dependency_table(actions,esc,links,table):
    rows=[]
    for a in actions:
        for rel in dependency_relations(a):
            rows.append([links([rel['predecessor_id']])+' → '+links([a['id']]),esc(RELATION_LABELS[rel['type']])+'<br>'+esc(GATE_LABELS[rel['gate']])+'<br>'+esc('確認済み' if rel.get('status')=='confirmed' else '提案・要確認'),esc(rel.get('condition') or rel['reason'])+'<p>'+esc(rel['reason'])+'</p>',esc(rel.get('can_proceed') or '条件が整う前に進められる範囲は未確認'),esc(rel.get('if_deferred') or '必須の条件が整うまで、該当する段階へ進めない。'),esc(rel['source'])])
    return '<h4>必須条件と、後回しにした場合の制約</h4>'+table(['前の行動 → 次の行動','関係・必要な段階','必要な条件・理由','先に進められる範囲','後回しにした場合の制約','根拠'],rows) if rows else '<p>前後関係の記載はありません。条件なしで着手できるという意味ではありません。</p>'

def dependency_diagram(actions,esc,natural,label):
    layers=dependency_layers(actions)
    if not layers:return '<p>対応の記載がありません。</p>'
    width=len(layers)*225+30;height=max(map(len,layers))*145+70;pos={}
    markers=''.join(f'<marker id="dep-arrow-{gate}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path class="arrow gate-{gate}" d="M0 0 L10 5 L0 10 Z"/></marker>' for gate in GATE_LABELS)
    out=['<p class="dependency-legend"><strong>図の読み方</strong>：実線＝必須、破線＝任意、点線＝要確認。線と先端の色は、橙＝着手前、紫＝確定前、青緑＝実施・移行前、灰＝段階未確認を表します。すべての矢印が着手の完了待ちを意味するわけではありません。必要な段階と後回しの制約は図の下の表で確認してください。列は読みやすくするための配置で、開始日や一律の着手順ではありません。</p>',f'<div class="diagram"><svg role="img" aria-labelledby="dep-title dep-desc" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><title id="dep-title">対応の依存関係</title><desc id="dep-desc">必須、任意、要確認を線の種類で区別します。必須は指定された段階で条件を満たす必要があります。詳細は続く表を参照してください。</desc><defs>{markers}</defs>']
    for col,group in enumerate(layers):
        for row,a in enumerate(group):pos[a['id']]=(col*225+20,row*145+45)
    for a in actions:
        x,y=pos[a['id']]
        for rel in dependency_relations(a):
            dep=rel['predecessor_id'];dx,dy=pos[dep];sx=dx+180;sy=dy+57;ey=y+57;mid=(sx+x)/2
            caption=RELATION_LABELS[rel['type']]+' / '+GATE_LABELS[rel['gate']]+' / '+rel['reason']+' / 後回しの制約: '+str(rel.get('if_deferred') or '必須の段階へは進めない')
            out.append(f'<path class="edge relation-{rel["type"]} gate-{rel["gate"]}" data-kind="{rel["type"]}" data-gate="{rel["gate"]}" data-from="{esc(dep)}" data-to="{esc(a["id"])}" d="M{sx} {sy} C{mid} {sy},{mid} {ey},{x-4} {ey}" marker-end="url(#dep-arrow-{rel["gate"]})"><title>{esc(caption)}</title></path>')
    for a in actions:
        x,y=pos[a['id']];title=natural(a.get('title',''));lines=[title[n:n+12] for n in range(0,len(title),12)]
        out.append(f'<a href="#{esc(a["id"])}"><g data-action="{esc(a["id"])}"><title>{esc(a["title"])} / 個別の条件を確認</title><rect class="node {"critical-node" if a.get("priority")=="critical" else ""}" x="{x}" y="{y}" width="180" height="115" rx="10"/><text x="{x+12}" y="{y+20}" font-size="12" font-weight="700">{esc(a["id"])} · {label(a.get("priority","unknown"))}</text>')
        for n,line in enumerate(lines[:4]):out.append(f'<text x="{x+12}" y="{y+42+n*16}" font-size="12">{esc(line)}{"…" if n==3 and len(lines)>4 else ""}</text>')
        out.append('</g></a>')
    return ''.join(out)+'</svg></div>'

def schedule_diagram(data,actions,esc,label,links,table):
    schedule=data.get('schedule') or {};rows=schedule.get('tasks',[])
    if not rows: return '<div class="callout"><strong>日程は未確定です。</strong><p>まず前後関係と並行できる候補を確認し、開始日・所要時間・担当の空きを対話で決めてから日程表を作ります。</p></div>'
    by_id={a['id']:a for a in actions};dated={};out=['<h3>日程案</h3><p>'+esc(schedule.get('basis','利用者と確認した条件に基づく日程案'))+'</p><p class="muted">終了日は作業が終わった直後の境界です。帯の長さは暦日の経過を表し、実作業時間や進捗率ではありません。</p>']
    for row in rows:
        i=row['action_id']
        if i not in by_id or i in dated: raise ValueError('Unknown or duplicate schedule task: '+i)
        start=date.fromisoformat(row['start']);end=date.fromisoformat(row['end'])
        if end<start: raise ValueError('End before start: '+i)
        dated[i]=(start,end,row)
    for i,(start,end,row) in dated.items():
        for dep in schedule_predecessors(by_id[i]):
            if dep not in dated: raise ValueError('Missing scheduled predecessor: '+dep)
            if dated[dep][1]>start: raise ValueError('Schedule violates dependency: '+dep+' -> '+i)
    low=min(x[0] for x in dated.values());high=max(x[1] for x in dated.values());span=max((high-low).days,1);w=1120;h=65+len(rows)*40
    out.append(f'<div class="diagram"><svg role="img" aria-labelledby="schedule-title" width="{w}" height="{h}" viewBox="0 0 {w} {h}"><title id="schedule-title">確認した条件に基づく日程案</title>')
    for n in range(5):
        x=330+n*170;d=low.fromordinal(low.toordinal()+round(span*n/4))
        out.append(f'<path class="grid" d="M{x} 35 V{h}"/><text x="{x}" y="22" font-size="12">{d.isoformat()}</text>')
    for n,row in enumerate(rows):
        i=row['action_id'];s,e,_=dated[i];y=52+n*40;x=330+680*(s-low).days/span;length=max(3,680*(e-s).days/span)
        out.append(f'<a href="#{esc(i)}"><text x="10" y="{y+17}" font-size="12">{esc(i)} {esc(by_id[i]["title"][:18])}</text><rect class="bar" x="{x}" y="{y}" width="{length}" height="24" rx="4"><title>{esc(i)} {s}〜{e} / {label(row.get("status","proposed"))}</title></rect></a>')
    out.append('</svg></div>')
    out.append(table(['対応','開始','終了（境界）','確定状況'],[[links([r['action_id']]),esc(r['start']),esc(r['end']),label(r.get('status','proposed'))] for r in rows]))
    return ''.join(out)
