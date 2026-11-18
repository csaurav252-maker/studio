import shutil
import tempfile
from pathlib import Path

import streamlit as st

import video_maker as vm

st.set_page_config(page_title="Documentary Video Maker", page_icon="🎬")
st.title("🎬 Documentary Video Maker")
st.caption("Script + images dya, voiceover ani subtitles sahit video milel.")

script = st.text_area(
    "Script (scenes blank line ne vegle kara)",
    height=250,
    placeholder="Scene 1 cha text... [IMG: english madhe image cha vichar]\n\nScene 2 cha text... [IMG: ...]",
)
images = st.file_uploader("Images (optional - nasatil tar AI aapoaap images banvel)",
                          type=["png", "jpg", "jpeg", "webp"], accept_multiple_files=True)
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
    for f in sorted(images, key=lambda x: x.name):
        (tmp / "images" / f.name).write_bytes(f.getvalue())
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
