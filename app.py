import os
import shutil
import tempfile
from pathlib import Path

import streamlit as st

import video_maker as vm

try:
    for _k in ("GEMINI_API_KEY", "GEMINI_IMAGE_MODEL", "GEMINI_TEXT_MODEL", "POLLINATIONS_KEY"):
        if _k in st.secrets:
            os.environ[_k] = st.secrets[_k]
except Exception:
    pass

st.set_page_config(page_title="Documentary Video Maker", page_icon="🎬")
st.title("🎬 Documentary Video Maker")
st.caption("Script + images dya, voiceover ani subtitles sahit video milel.")

script = st.text_area(
    "Script (scenes blank line ne vegle kara). Images AI aapoaap banvel.",
    height=250,
    placeholder="Scene 1 cha text...\n\nScene 2 cha text...",
)
images = st.file_uploader("Images (optional - nasatil tar AI aapoaap images banvel)",
                          type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True)
# Images cha kram app madhech thara (file che nav badlaychi garaj nahi)
order = {}
if images:
    st.write("**Images cha kram thara** (1 = pahili scenes, 2 = pudhchya scenes ...)")
    cols = st.columns(min(4, len(images)))
    for i, f in enumerate(images):
        with cols[i % len(cols)]:
            st.image(f, use_container_width=True)
            order[i] = st.number_input("Kram", min_value=1, max_value=len(images),
                                       value=i + 1, step=1, key=f"ord_{i}_{f.name}")

music = st.file_uploader("Background music (optional)", type=["mp3", "wav", "m4a"])

col1, col2 = st.columns(2)
voice = col1.selectbox("Voice", ["hi-IN-MadhurNeural", "hi-IN-SwaraNeural",
                                 "mr-IN-ManoharNeural", "mr-IN-AarohiNeural"])
quality = col2.selectbox("Format", ["Short 9:16 (Reels/Shorts)", "Wide 16:9 (YouTube)"])

if st.button("Video banva", type="primary"):
    if not script.strip():
        st.error("Aadhi script lihā.")
        st.stop()
    if quality.startswith("Short"):
        vm.set_resolution(720, 1280)
    else:
        vm.set_resolution(1280, 720)
    tmp = Path(tempfile.mkdtemp())
    (tmp / "images").mkdir()
    (tmp / "script.txt").write_text(script, encoding="utf-8")
    ranked = sorted(range(len(images)), key=lambda i: (order.get(i, i + 1), i))
    for rank, i in enumerate(ranked, start=1):
        f = images[i]
        (tmp / "images" / f"{rank:03d}{Path(f.name).suffix.lower()}").write_bytes(f.getvalue())
    if music:
        (tmp / f"music{Path(music.name).suffix}").write_bytes(music.getvalue())
    box = st.empty()
    lines = []

    def log(m):
        lines.append(m)
        box.code("\n".join(lines[-8:]))

    try:
        with st.spinner("Video banto... thoda vel lagel"):
            out = vm.build(tmp, voice=voice, log=log)
        st.success("Video tayar!")
        data = out.read_bytes()
        st.video(data)
        st.download_button("Download MP4", data, file_name="output.mp4", mime="video/mp4")
    except Exception as e:
        st.error(str(e))
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    problems = [l for l in lines if l.startswith("!")]
    if problems:
        st.warning("Kahi goshti chalalya nahit:\n\n" + "\n\n".join(problems[:6]))
    with st.expander("Purna log (kahi problem asel tar ha mala paste kara)"):
        st.code("\n".join(lines))
