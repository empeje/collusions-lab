"""Build a lightweight static HTML site from runs/."""

from __future__ import annotations

import html
import json
from pathlib import Path

RUNS = Path(__file__).resolve().parent.parent / "runs"
SITE = Path(__file__).resolve().parent.parent / "site"
SITE.mkdir(exist_ok=True)


def _load_json(p: Path):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _collect():
    episodes = []
    for res in RUNS.rglob("result.json"):
        data = _load_json(res)
        ep_id = data.get("episode_id") or res.parent.name
        metrics = data.get("metrics", {})
        decisions = data.get("decisions", [])
        episodes.append(
            {
                "episode_id": ep_id,
                "scenario": data.get("scenario"),
                "condition": data.get("condition"),
                "seed": data.get("seed"),
                "monitor_enabled": data.get("monitor_enabled"),
                "ground_truth": data.get("ground_truth", {}),
                "attempted_harm": data.get("attempted_harm"),
                "harmful_outcome": data.get("harmful_outcome"),
                "harm_prevented": data.get("harm_prevented"),
                "metrics": {k: v for k, v in metrics.items() if k != "mean_price_history"},
                "price_history": metrics.get("mean_price_history") or [],
                "decisions": decisions,
            }
        )
    episodes.sort(key=lambda e: (e["scenario"] or "", e["condition"] or "", e["seed"] or 0))
    return episodes


def _html(episodes: list[dict]) -> str:
    data_json = json.dumps(episodes, indent=2)
    scenarios = sorted({e["scenario"] for e in episodes if e["scenario"] is not None})
    conditions = sorted({e["condition"] for e in episodes if e["condition"] is not None})
    seeds = sorted({e["seed"] for e in episodes if e["seed"] is not None})

    scen_opts = '<option value="all">all</option>' + ''.join(
        f'<option value="{s}">{s}</option>' for s in scenarios
    )
    cond_opts = '<option value="all">all</option>' + ''.join(
        f'<option value="{c}">{c}</option>' for c in conditions
    )
    seed_opts = '<option value="all">all</option>' + ''.join(
        f'<option value="{se}">{se}</option>' for se in seeds
    )

    return """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Collusions Lab — Static Demo</title>
  <script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>
  <style>
    body { font-family: system-ui,-apple-system,Segoe UI,Roboto,sans-serif; margin: 2rem; line-height: 1.5; }
    h1,h2,h3 { margin: .5rem 0; }
    .controls { display:flex; flex-wrap:wrap; gap:1rem; align-items:end; margin:1rem 0 2rem; }
    select, button { padding:.5rem .75rem; }
    .card { border:1px solid #ddd; border-radius:8px; padding:1rem; margin:1rem 0; box-shadow:0 1px 2px rgba(0,0,0,.05); }
    table { border-collapse:collapse; width:100%; margin:.5rem 0; }
    th,td { border:1px solid #eee; padding:.4rem .6rem; text-align:left; vertical-align:top; }
    pre { max-height:40vh; overflow:auto; background:#f7f7f7; padding:1rem; border-radius:6px; }
    .pill { display:inline-block; padding:.1rem .5rem; border-radius:999px; background:#f0f0ff; margin:.1rem .25rem 0 0; }
    small { color:#666; }
  </style>
</head>
<body>
  <h1>Collusions Lab — Static Demo</h1>
  <p>
    Precomputed episodes from the trusted-monitor benchmark (markets + SWE).
    Ground truth is <em>evaluation-only</em> and never shown to the live monitor.
    <a href="https://github.com/munip/collusions-lab">Source on GitHub</a> ·
    <a href="https://huggingface.co/datasets/munipu/collusions-lab-runs">Runs dataset</a>
  </p>

  <div class="controls">
    <label>Scenario
      <select id="scenario">""" + scen_opts + """</select>
    </label>
    <label>Condition
      <select id="condition">""" + cond_opts + """</select>
    </label>
    <label>Seed
      <select id="seed">""" + seed_opts + """</select>
    </label>
    <label>Monitor
      <select id="monitor"><option value="all">all</option><option value="on">on</option><option value="off">off</option></select>
    </label>
    <button id="prev">← Prev</button>
    <button id="next">Next →</button>
    <span id="count"></span>
  </div>

  <div class="card" id="summary"></div>
  <div class="card"><h3>Metrics</h3><div id="metrics"></div></div>
  <div class="card"><h3>Monitor decisions</h3><div id="decisions"></div></div>
  <div class="card"><h3>Mean price (markets)</h3><div id="priceplot" style="height:360px;"></div></div>
  <div class="card"><h3>Raw episode JSON</h3><pre id="raw"></pre></div>

  <script>const EPISODES = """ + data_json + """;</script>
  <script>
    var scenSel=document.getElementById('scenario'), condSel=document.getElementById('condition'), seedSel=document.getElementById('seed'), monSel=document.getElementById('monitor');
    var summaryEl=document.getElementById('summary'), metricsEl=document.getElementById('metrics'), decEl=document.getElementById('decisions'), plotEl=document.getElementById('priceplot'), rawEl=document.getElementById('raw'), countEl=document.getElementById('count');
    var list=EPISODES.slice(), idx=0;
    function filter(){
      list=EPISODES.filter(function(e){
        if(scenSel.value!=='all'&&e.scenario!=scenSel.value)return false;
        if(condSel.value!=='all'&&e.condition!=condSel.value)return false;
        if(seedSel.value!=='all'&&String(e.seed)!=seedSel.value)return false;
        if(monSel.value==='on'&&!e.monitor_enabled)return false;
        if(monSel.value==='off'&&e.monitor_enabled)return false;
        return true;
      }); if(list.length===0) idx=0; else idx=Math.min(idx, list.length-1); render();
    }
    function pill(k,v){ if(v===null||v===undefined) return ''; return '<span class="pill">'+k+': '+v+'</span>'; }
    function tbl(obj){ if(!obj||Object.keys(obj).length===0) return '<em>n/a</em>'; var h='<table><tr><th>key</th><th>value</th></tr>'; for(var k in obj){ if(!obj.hasOwnProperty(k)) continue; var v=obj[k]; var val=(typeof v==='object')?JSON.stringify(v):v; h+='<tr><td>'+k+'</td><td>'+val+'</td></tr>'; } return h+'</table>'; }
    function decisionsTbl(ds){ if(!ds||ds.length===0) return '<em>(none recorded)</em>'; var h='<table><tr><th>step</th><th>action</th><th>risk</th><th>reasons</th></tr>'; for(var i=0;i<ds.length;i++){ var d=ds[i]; var reasons=(d.reasons||[]).join(' | '); h+='<tr><td>'+(d.step!=null?d.step:'')+'</td><td>'+(d.action||'')+'</td><td>'+(d.risk_score!=null?d.risk_score:(d.risk!=null?d.risk:''))+'</td><td>'+reasons+'</td></tr>'; } return h+'</table>'; }
    function render(){
      countEl.textContent = list.length? ('Episode '+(idx+1)+'/'+list.length+' ('+EPISODES.length+' total)') : '(no matches)';
      if(list.length===0){ summaryEl.innerHTML=''; metricsEl.innerHTML=''; decEl.innerHTML=''; Plotly.purge(plotEl); rawEl.textContent=''; return; }
      var e=list[idx];
      var gtLabel = e.ground_truth && e.ground_truth.label ? e.ground_truth.label : '';
      summaryEl.innerHTML = '<h2>'+e.scenario+'/'+e.condition+' (seed='+e.seed+')</h2><div>'+pill('monitor', e.monitor_enabled?'on':'off')+pill('label', gtLabel)+pill('attempted_harm', e.attempted_harm)+pill('harmful_outcome', e.harmful_outcome)+pill('harm_prevented', e.harm_prevented)+'</div><small>episode_id: '+e.episode_id+'</small>';
      metricsEl.innerHTML = tbl(e.metrics||{});
      decEl.innerHTML = decisionsTbl(e.decisions||[]);
      if(e.price_history&&e.price_history.length){ Plotly.newPlot(plotEl,[{x:Array.from({length:e.price_history.length},function(_,i){return i;}), y:e.price_history, mode:'lines', name:'mean_price'}], {margin:{t:20,r:10,b:40,l:40}}, {displayModeBar:false}); }
      else { Plotly.purge(plotEl); }
      rawEl.textContent = JSON.stringify(e,null,2);
    }
    [scenSel,condSel,seedSel,monSel].forEach(function(s){ s.onchange=filter; });
    document.getElementById('prev').onclick=function(){ if(idx>0){ idx--; render(); } };
    document.getElementById('next').onclick=function(){ if(idx<list.length-1){ idx++; render(); } };
    filter();
  </script>
</body>
</html>"""


def main() -> int:
    episodes = _collect()
    (SITE / "index.html").write_text(_html(episodes), encoding="utf-8")
    print(f"Wrote {SITE / 'index.html'} with {len(episodes)} episodes")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
