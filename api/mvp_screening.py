"""MVP clinical screening — QC gate + versioned contract over comprehensive_fundus."""
from __future__ import annotations

import logging
import os
import uuid

from fastapi import APIRouter, File, Form, HTTPException, Query, UploadFile, status
from fastapi.responses import HTMLResponse

from services.clinical_image_qc import inference_allowed, run_clinical_image_qc
from services.mvp_result_contract import SCHEMA_VERSION, build_mvp_result_from_comprehensive
from services.preprocessing_lock import PREPROCESSING_VERSION, SERVING_LOCKED_DEFAULT_MODE

log = logging.getLogger("api.mvp_screening")
router = APIRouter(tags=["mvp"])


def _review_policy() -> str:
    return os.getenv("MEDI_QC_REVIEW_POLICY", "block").strip().lower()


@router.post("/mvp/clinical-screening")
async def mvp_clinical_screening(
    file: UploadFile = File(...),
    eye: str = Form("R"),
    lang: str = Form("ko"),
    patient_id: str | None = Form(None),
    image_id: str | None = Form(None),
    tenant_id: str | None = Form(None),
    location_id: str | None = Form(None),
    include_heatmap: bool = Form(False),
    mode: str = Query("fast", description="fast=v10c | precise=specialists"),
    preprocess: str = Query(
        SERVING_LOCKED_DEFAULT_MODE,
        description="serving preprocess; v10c meta default none",
    ),
) -> dict:
    """Versioned clinical result for eyecare-platform consumers (MVP-03A).

    Data minimization: accept only technical IDs (tenant/location/image).
    Do not send patient name/contact to this endpoint for inference.
    """
    # PHI rule: ignore patient_id for logging/inference forwarding
    _ = patient_id
    # Neutralize client filename — never use potentially PII-bearing names
    image_bytes = await file.read()
    qc = run_clinical_image_qc(image_bytes, filename=None)
    if not inference_allowed(qc, review_policy=_review_policy()):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail={
                "error": "qc_blocked",
                "qc": qc,
                "schema_version": SCHEMA_VERSION,
                "review_policy": _review_policy(),
            },
        )

    trace_id = str(uuid.uuid4())
    img_id = image_id or str(uuid.uuid4())
    xai_failed = False
    try:
        from services.comprehensive_fundus import run_comprehensive_fundus

        result = await run_comprehensive_fundus(
            image_bytes,
            lang=lang,
            patient_id=None,
            eye=eye,
            include_heatmap=include_heatmap,
            tasks=["dr", "glaucoma", "amd", "myopia", "screening"],
            mode=mode,
            preprocess=preprocess or SERVING_LOCKED_DEFAULT_MODE,
        )
        payload = result.model_dump() if hasattr(result, "model_dump") else dict(result)
    except FileNotFoundError as exc:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"error": "model_unavailable", "message": str(exc), "trace_id": trace_id},
        ) from exc
    except Exception as exc:
        log.exception("mvp clinical screening failed trace_id=%s image_id=%s", trace_id, img_id)
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "error": "inference_unavailable",
                "message": str(exc)[:200],
                "trace_id": trace_id,
                "image_id": img_id,
            },
        ) from exc

    if include_heatmap:
        hm = payload.get("heatmap") or {}
        if not (isinstance(hm, dict) and any(hm.values())):
            xai_failed = True

    out = build_mvp_result_from_comprehensive(
        payload,
        eye=eye,
        trace_id=trace_id,
        qc=qc,
        image_id=img_id,
        include_heatmap=include_heatmap,
        xai_failed=xai_failed,
        preprocessing_version=PREPROCESSING_VERSION,
    )
    # Technical tenant context only (optional)
    if tenant_id or location_id:
        out["tenant_context"] = {
            "tenant_id": tenant_id,
            "location_id": location_id,
            "note": "technical IDs only — no PHI",
        }
        out["grade_raw"]["tenant_id"] = tenant_id
        out["grade_raw"]["location_id"] = location_id
    return out


@router.get("/mvp/pilot-console", response_class=HTMLResponse)
async def mvp_pilot_console() -> str:
    """Minimal operator UI — no PHI fields; technical IDs only."""
    return """<!doctype html>
<html lang="ko"><head><meta charset="utf-8"/>
<title>MVP-02 Pilot Console (NON-REGULATORY)</title>
<style>
body{font-family:system-ui,sans-serif;max-width:880px;margin:24px auto;padding:0 16px;background:#0f1419;color:#e7ecf1}
h1{font-size:1.25rem} .box{background:#1a222c;padding:16px;border-radius:8px;margin:12px 0}
.revise{color:#ffb020;font-weight:700;font-size:1.4rem}
.pass{color:#3dd68c;font-weight:700} .fail{color:#f07178}
.stub{outline:3px dashed #f07178;padding:8px} label{display:block;margin:8px 0 4px}
button{background:#3d8bfd;color:#fff;border:0;padding:10px 16px;border-radius:6px;cursor:pointer}
pre{white-space:pre-wrap;word-break:break-word;font-size:12px}
.note{color:#9aa4b2;font-size:12px}
</style></head><body>
<h1>MVP-02 Pilot Screening Console</h1>
<p class="note">Engineering console only. No regulatory claim. Do not enter PHI (name/phone/MRN).</p>
<div class="box">
<label>Technical subject ref (optional UUID)</label>
<input id="subj" style="width:100%;padding:8px" placeholder="leave blank to auto-generate"/>
<label>Eye</label>
<select id="eye"><option>R</option><option>L</option></select>
<label>Fundus image (JPEG/PNG)</label>
<input id="file" type="file" accept="image/*"/>
<label><input id="xai" type="checkbox"/> Request XAI (GradCAM)</label>
<button id="go">Run QC → MEDI inference</button>
</div>
<div class="box" id="out">Waiting…</div>
<script>
const out=document.getElementById('out');
document.getElementById('go').onclick=async()=>{
  const f=document.getElementById('file').files[0];
  if(!f){out.innerHTML='<span class=fail>Select an image</span>';return;}
  out.textContent='Running…';
  const fd=new FormData();
  fd.append('file', f);
  fd.append('eye', document.getElementById('eye').value);
  fd.append('include_heatmap', document.getElementById('xai').checked ? 'true' : 'false');
  const subj=document.getElementById('subj').value.trim();
  if(subj) fd.append('image_id', subj);
  try{
    const r=await fetch('/api/v1/mvp/clinical-screening?mode=fast&preprocess=none',{method:'POST',body:fd});
    const j=await r.json();
    if(!r.ok){
      out.innerHTML='<div class=fail>HTTP '+r.status+'</div><pre>'+JSON.stringify(j,null,2)+'</pre>';
      return;
    }
    const dec=j.decision||'';
    const cls=dec==='REVISE'?'revise':(dec==='PASS'?'pass':'fail');
    const clinical=j.clinical_mode||'';
    const wrap=clinical==='CLINICAL'?'':'stub';
    out.innerHTML=`<div class="${wrap}">
      <div>QC: <b>${(j.qc&&j.qc.qc_status)||'?'}</b> (${(j.qc&&j.qc.qc_version)||''})</div>
      <div>clinical_mode: <b>${clinical}</b></div>
      <div>model: ${j.model_version||''}</div>
      <div>preprocessing: ${j.preprocessing_version||''}</div>
      <div class="${cls}">decision: ${dec}</div>
      <div>confidence: ${j.confidence}</div>
      <div>reason: ${j.reason||''}</div>
      <div>risk_flag: ${j.risk_flag||''}</div>
      <div>xai_status: ${j.xai_status||''}</div>
      <div>image_id: ${j.image_id||''}</div>
      <div>trace_id: ${j.trace_id||''}</div>
      <pre>${JSON.stringify({disease_labels:j.disease_labels,qc_reasons:(j.qc&&j.qc.qc_reasons)},null,2)}</pre>
    </div>`;
  }catch(e){out.innerHTML='<span class=fail>'+e+'</span>';}
};
</script>
</body></html>"""
