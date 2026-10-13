"""Verified Japanese workday calendar; no network access or guessed estimates."""
from datetime import date, timedelta
from planning_report import schedule_diagram as calendar_day_diagram, schedule_predecessors, validate_dependencies

SOURCE = 'https://www8.cao.go.jp/chosei/shukujitsu/gaiyou.html'
VERIFIED_ON = '2026-10-04'
HOLIDAYS = {
    2026: '01-01 01-12 02-11 02-23 03-20 04-29 05-03 05-04 05-05 05-06 07-20 08-11 09-21 09-22 09-23 10-12 11-03 11-23'.split(),
    2027: '01-01 01-11 02-11 02-23 03-21 03-22 04-29 05-03 05-04 05-05 07-19 08-11 09-20 09-23 10-11 11-03 11-23'.split(),
}

def is_workday(day, extra_holidays=()):
    if isinstance(day, str): day = date.fromisoformat(day)
    if day.year not in HOLIDAYS:
        raise ValueError('祝日を確認していない年です: ' + str(day.year))
    return day.weekday() < 5 and day.strftime('%m-%d') not in HOLIDAYS[day.year] and day.isoformat() not in set(extra_holidays)

def next_workday(day, extra_holidays=()):
    if isinstance(day, str): day = date.fromisoformat(day)
    while not is_workday(day, extra_holidays): day += timedelta(days=1)
    return day

def business_span(start, duration_business_days, extra_holidays=()):
    if isinstance(duration_business_days, bool) or not isinstance(duration_business_days, int) or duration_business_days <= 0:
        raise ValueError('所要日数は根拠のある正の整数営業日で指定してください。未定を1日に置き換えません。')
    current = next_workday(start, extra_holidays); work_dates = []
    for _ in range(duration_business_days):
        work_dates.append(current.isoformat())
        current = next_workday(current + timedelta(days=1), extra_holidays)
    return {'start': work_dates[0], 'last_work_date': work_dates[-1], 'end': current.isoformat(),
            'duration_business_days': duration_business_days, 'work_dates': work_dates}

def serial_schedule(actions, sequence, estimates, start, owner, extra_holidays=(), status='proposed'):
    """Only for an explicitly agreed single-owner, capacity-one plan, without wait time."""
    if not owner: raise ValueError('担当者と同時作業上限1の確認が必要です。')
    by_id = validate_dependencies(actions)
    if len(by_id) != len(actions) or len(sequence) != len(set(sequence)) or set(sequence) != set(by_id):
        raise ValueError('実行順に全対応を一回ずつ指定してください。')
    tasks = []; completed = {}; cursor = next_workday(start, extra_holidays)
    for i in sequence:
        if any(d not in completed for d in schedule_predecessors(by_id[i])):
            raise ValueError('実行順が先行条件に反しています: ' + i)
        estimate = estimates.get(i) or {}
        if not estimate.get('source'): raise ValueError('見積の根拠が必要です: ' + i)
        span = business_span(cursor, estimate.get('duration_business_days'), extra_holidays)
        tasks.append(dict(span, action_id=i, owner=owner, estimate_source=estimate['source'], status=status))
        completed[i] = span['end']; cursor = date.fromisoformat(span['end'])
    return {'basis': '土日と日本の祝日・休日を除く営業日。確認した作業別見積と実行順に従い、同じ担当者が一件ずつ実施。承認待ちは別途確認。',
            'calendar': {'mode': 'japan_business_days', 'source': SOURCE, 'verified_on': VERIFIED_ON,
                         'verified_years': sorted(HOLIDAYS), 'extra_holidays': list(extra_holidays)},
            'resource_constraints': {'owner': owner, 'concurrency': 1}, 'tasks': tasks}

def schedule_diagram(data, actions, esc, label, links, table):
    schedule = data.get('schedule') or {}; rows = schedule.get('tasks', [])
    if not rows:
        return '<div class="callout"><strong>日程は未確定です。</strong><p>各対応の所要日数と見積の根拠、開始日、担当の空き、承認待ちを確認してから、土日と日本の祝日を除く営業日で日程を作ります。一律1営業日とは仮定しません。</p></div>'
    calendar = schedule.get('calendar') or {}
    if calendar.get('mode') != 'japan_business_days':
        return calendar_day_diagram(data, actions, esc, label, links, table)
    if calendar.get('source') != SOURCE or calendar.get('verified_on') != VERIFIED_ON:
        raise ValueError('カレンダーの出典・確認日が登録データと一致しません。')
    extra = calendar.get('extra_holidays', []); by_id = {a['id']: a for a in actions}; dated = {}
    for row in rows:
        i = row['action_id']
        if i not in by_id or i in dated: raise ValueError('日程に未知または重複する対応があります: ' + i)
        if not row.get('estimate_source'): raise ValueError('見積根拠がありません: ' + i)
        expected = business_span(row['start'], row.get('duration_business_days'), extra)
        if any(row.get(k) != expected[k] for k in expected): raise ValueError('営業日または完了日が一致しません: ' + i)
        dated[i] = (date.fromisoformat(row['start']), date.fromisoformat(row['end']), row)
    for i, (start, end, row) in dated.items():
        for dep in schedule_predecessors(by_id[i]):
            if dep not in dated or dated[dep][1] > start: raise ValueError('先行作業と日程が矛盾します: ' + i)
    resources = schedule.get('resource_constraints') or {}
    if resources.get('concurrency') == 1:
        for i, (s, e, r) in dated.items():
            for j, (s2, e2, r2) in dated.items():
                if i < j and r.get('owner') and r.get('owner') == r2.get('owner') and max(s, s2) < min(e, e2):
                    raise ValueError('同じ担当者の作業が重複しています: ' + i + '/' + j)
    low = min(v[0] for v in dated.values()); high = max(v[1] for v in dated.values())
    span = max((high-low).days, 1); width = 1120; height = 65 + 40*len(rows)
    out = ['<h3>営業日で整理した日程案</h3><p>' + esc(schedule.get('basis')) + '</p>',
           '<p class="muted">横軸は日付です。灰色は土日・祝日・追加の休業日で、色の帯が作業日です。完了日は最後の作業日、後続開始可能日はその次の営業日です。帯は進捗率ではありません。</p>',
           '<p>祝日の出典: <a href="' + SOURCE + '">内閣府の祝日・休日一覧</a>（確認日 ' + VERIFIED_ON + '、2026・2027年）。会社独自の休業日: ' + esc('、'.join(extra) or '追加指定なし') + '</p>',
           f'<div class="diagram"><svg role="img" aria-labelledby="schedule-title" width="{width}" height="{height}" viewBox="0 0 {width} {height}"><title id="schedule-title">営業日と休業日を区別した日程案</title>']
    for n in range(span):
        d = low + timedelta(days=n); x = 330 + 680*n/span
        if not is_workday(d, extra): out.append(f'<rect class="nonworking" x="{x}" y="35" width="{680/span}" height="{height-35}" fill="var(--tint)"><title>{d} 休業日</title></rect>')
    for n in range(5):
        x = 330+n*170; d = low + timedelta(days=round(span*n/4))
        out.append(f'<path class="grid" d="M{x} 35 V{height}"/><text x="{x}" y="22" font-size="12">{d.isoformat()}</text>')
    for n, row in enumerate(rows):
        i = row['action_id']; y = 52+n*40
        out.append(f'<a href="#{esc(i)}"><text x="10" y="{y+17}" font-size="12">{esc(i)} {esc(by_id[i]["title"][:18])}</text>')
        for day in row['work_dates']:
            x = 330+680*(date.fromisoformat(day)-low).days/span
            out.append(f'<rect class="bar" data-action="{esc(i)}" data-work-date="{day}" x="{x}" y="{y}" width="{max(2,680/span-1)}" height="24" rx="2"><title>{esc(i)} {day} / {row["duration_business_days"]}営業日 / {label(row.get("status","proposed"))}</title></rect>')
        out.append('</a>')
    out.append('</svg></div>')
    out.append(table(['対応','所要日数・見積根拠','開始','完了','後続開始可能','状態'], [[links([r['action_id']]), esc(str(r['duration_business_days'])+'営業日')+'<br>'+esc(r['estimate_source']), esc(r['start']), esc(r['last_work_date']), esc(r['end']), label(r.get('status','proposed'))] for r in rows]))
    return ''.join(out)
