# -*- coding: utf-8 -*-
"""CRM BĐS backend: serve PWA + /api/transcribe (STT tiếng Việt + AI tổng hợp)."""
import os, re, json, subprocess, threading, time, shutil, random
from flask import Flask, request, jsonify, send_from_directory

BASE = os.path.dirname(os.path.abspath(__file__))
UPLOAD = os.path.join(os.environ.get("HERMES_HOME", r"D:\Hermes"), "cache", "scratch", "crm_uploads")
os.makedirs(UPLOAD, exist_ok=True)

MODEL = os.environ.get("CRM_WHISPER_MODEL", "small")
HERMES = os.environ.get("CRM_HERMES_CMD") or shutil.which("hermes") or \
         r"D:\Hermes\hermes-agent\apps\desktop\release\win-unpacked\resources\agent-payload\bin\hermes.exe"
AI_MODEL = os.environ.get("CRM_HERMES_MODEL", "glm-5.3-flash")

app = Flask(__name__, static_folder=BASE, static_url_path="")
app.config["MAX_CONTENT_LENGTH"] = 200 * 1024 * 1024

_model = None
_lock = threading.Lock()
JOBS = {}
JOBS_LOCK = threading.Lock()
_STT_LOCK = threading.Lock()


def run_job(jid, path):
    try:
        with _STT_LOCK:
            text = stt(path)
        try:
            with open(os.path.join(BASE, "job_debug.log"), "a", encoding="utf-8") as dbg:
                dbg.write("job %s text_len=%s\n" % (jid, len(text)))
        except OSError:
            pass
        # kết quả nhanh (rule) → app hiện ngay; AI chạy nền rồi cập nhật
        fast = rule_analyze(text)
        fast["ai_status"] = "pending"
        with JOBS_LOCK:
            JOBS[jid] = {"ok": True, "status": "done", "text": text, "analysis": fast, "model": MODEL}
        ai = ai_analyze(text)
        with JOBS_LOCK:
            if jid not in JOBS:
                return
            if ai.get("error"):
                JOBS[jid]["ai_status"] = "failed"
                JOBS[jid]["ai_error"] = ai.get("error")
            else:
                ai["ai_status"] = "done"
                JOBS[jid]["analysis"] = ai
                JOBS[jid]["ai_status"] = "done"
    except Exception as e:
        with JOBS_LOCK:
            JOBS[jid] = {"ok": False, "status": "error", "error": str(e)}
    finally:
        try:
            os.remove(path)
        except OSError:
            pass


def get_model():
    global _model
    if _model is None:
        with _lock:
            if _model is None:
                from faster_whisper import WhisperModel
                print("[crm] loading whisper model:", MODEL, flush=True)
                _model = WhisperModel(MODEL, device="cpu", compute_type="int8")
    return _model


def decode_wav(path):
    import wave
    import numpy as np
    wav = path + ".16k.wav"
    subprocess.run(["ffmpeg", "-y", "-i", path, "-ac", "1", "-ar", "16000", "-f", "wav", wav],
                   check=True, capture_output=True)
    w = wave.open(wav, "rb")
    frames = w.readframes(w.getnframes())
    w.close()
    try:
        os.remove(wav)
    except OSError:
        pass
    return np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0


def stt(path):
    def lg(m):
        try:
            with open(os.path.join(BASE, "job_debug.log"), "a", encoding="utf-8") as dbg:
                dbg.write(m + "\n")
        except OSError:
            pass
    lg("stt begin %s" % path)
    audio = decode_wav(path)
    lg("stt decoded %s" % (audio.shape,))
    segs, info = get_model().transcribe(audio, language="vi", beam_size=1)
    out = "".join(s.text for s in segs).strip()
    lg("stt done len=%s" % len(out))
    return out


PROMPT = """Bạn là trợ lý CRM bất động sản. Phân tích bản chép cuộc gọi sau và trả về CHÍNH XÁC một object JSON (không markdown, không giải thích) với các khóa:
tom_tat: string (1-2 câu tóm tắt nhu cầu, ý định của khách),
nhu_cau: "Mua" hoặc "Thuê",
so_phong_ngu: số (0 nếu không rõ),
dien_tich: string (vd "70 m2"),
khu_vuc: string (để "" nếu không rõ),
ngan_sach: string,
yeu_cau_dac_biet: mảng string,
uu_tien: "Cao" hoặc "Trung bình" hoặc "Thấp",
trang_thai_de_xuat: một trong "Mới","Đã gọi","Đẹp","Đã xem nhà","Chốt","Chặn",
buoc_tiep_theo: string (hành động cần làm, kèm thời gian nếu có),
ghi_chu: string.
Chỉ dùng thông tin có trong bản chép; không bịa.
Bản chép: %s"""


def ai_analyze(text):
    prompt = PROMPT % text
    last = None
    for attempt in range(3):
        t = time.time()
        try:
            cmd = [HERMES]
            if AI_MODEL:
                cmd += ["-m", AI_MODEL]
            cmd += ["-z", prompt]
            r = subprocess.run(cmd, capture_output=True, text=True,
                               timeout=300, encoding="utf-8", errors="replace")
            out = (r.stdout or "") + (r.stderr or "")
            try:
                with open(os.path.join(BASE, "ai_debug.log"), "a", encoding="utf-8") as dbg:
                    dbg.write("---- try=%s rc=%s dt=%.1f prompt_len=%s prompt_tail=%r\n%s\n"
                              % (attempt, r.returncode, time.time() - t, len(prompt), prompt[-160:], out[:900]))
            except OSError:
                pass
            m = re.search(r"\{.*\}", out, re.S)
            if m:
                try:
                    return json.loads(m.group(0))
                except Exception as e:
                    last = {"error": "json: " + str(e), "raw": out[-500:]}
            else:
                last = {"error": "khong doc duoc JSON", "raw": out[-500:]}
        except Exception as e:
            last = {"error": str(e)}
    return last or {"error": "unknown"}


def rule_analyze(text):
    t = text.lower()

    def find(p, default=""):
        m = re.search(p, t)
        return m.group(1).strip() if m else default

    phong = find(r"(\d+)\s*phòng")
    dt = find(r"(\d+)\s*(?:m2|m²|met|mét)")
    gia = find(r"(\d+[.,]?\d*)\s*(tỷ|triệu)")
    gia = gia.replace(".", ",") if gia else ""
    quan = find(r"quận\s*([a-z0-9à-ỹ]+)")
    nhu = "Thuê" if "thuê" in t else "Mua"
    special = [k for k in ["căn góc", "hướng đông nam", "hướng tây", "hầm xe", "gần trường", "gần công viên", "thang máy", "ban công"] if k in t]
    return {
        "tom_tat": text[:160],
        "nhu_cau": nhu,
        "so_phong_ngu": int(phong) if phong else 0,
        "dien_tich": (dt + " m2") if dt else "",
        "khu_vuc": ("Quận " + quan) if quan else "",
        "ngan_sach": gia,
        "yeu_cau_dac_biet": special,
        "uu_tien": "Trung bình",
        "trang_thai_de_xuat": "Đã gọi",
        "buoc_tiep_theo": "",
        "ghi_chu": "",
        "fallback": True,
    }


@app.after_request
def cors(resp):
    resp.headers["Access-Control-Allow-Origin"] = "*"
    resp.headers["Access-Control-Allow-Headers"] = "Content-Type"
    resp.headers["Access-Control-Allow-Methods"] = "GET,POST,OPTIONS"
    return resp


@app.route("/")
def index():
    return send_from_directory(BASE, "index.html")


@app.route("/<path:p>")
def static_files(p):
    return send_from_directory(BASE, p)


@app.route("/api/transcribe", methods=["POST", "OPTIONS"])
def transcribe():
    if request.method == "OPTIONS":
        return "", 204
    f = request.files.get("audio")
    if not f:
        return jsonify({"error": "khong co file"}), 400
    ext = os.path.splitext(f.filename or "")[1].lower() or ".mp3"
    jid = str(int(time.time() * 1000)) + str(random.randint(100, 999))
    path = os.path.join(UPLOAD, jid + ext)
    f.save(path)
    try:
        sz = os.path.getsize(path)
    except OSError:
        sz = -1
    try:
        with open(os.path.join(BASE, "job_debug.log"), "a", encoding="utf-8") as dbg:
            dbg.write("job %s name=%s size=%s\n" % (jid, f.filename, sz))
    except OSError:
        pass
    with JOBS_LOCK:
        JOBS[jid] = {"ok": True, "status": "running"}
    threading.Thread(target=run_job, args=(jid, path), daemon=True).start()
    return jsonify({"ok": True, "job": jid})


@app.route("/api/transcribe/<jid>")
def transcribe_status(jid):
    with JOBS_LOCK:
        j = JOBS.get(jid)
    if not j:
        return jsonify({"ok": False, "error": "khong thay job"}), 404
    return jsonify(j)


if __name__ == "__main__":
    print("[crm] serving %s on http://127.0.0.1:8080 (model=%s)" % (BASE, MODEL), flush=True)
    app.run(host="127.0.0.1", port=8080, threaded=True, debug=False)
