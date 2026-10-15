# Video portfolio

Nguồn video 180 giây, 1280×720, chữ tiếng Việt; không lồng tiếng. Nền tối theo
Metabase, số liệu dựa trên evidence ngày 15/10/2026. Đây là video trình bày
kiến trúc và kết quả kiểm tra, không giả thành một screen recording trực tiếp.

```bash
.venv/bin/python -m pip install -r demo/requirements-render.txt
bash scripts/render_demo.sh
```

HyperFrames pin 0.8.162, GSAP 3.14.2 và font được lưu local (kèm OFL license).
`npx hyperframes@0.8.162 check demo` kiểm tra runtime/layout/motion/contrast.
FFmpeg dùng bản imageio-ffmpeg nếu hệ thống thiếu libx264.

Video kết quả: docs/legacy-migration-demo.mp4. Cần cập nhật scene trạng thái
ngày xanh và CI nếu làm video bàn giao sau này, không biến 1/5 thành 5/5 bằng tay.
