# CRM BĐS — Chăm sóc khách (PWA)

App CRM bất động sản chạy trên điện thoại, cài như app thật (PWA), dữ liệu lưu ngay trên thiết bị.

## Link đang chạy (chiều nay)
https://oliver-employers-ladies-equivalent.trycloudflare.com/index.html

> Link này sống khi PC bật và `cloudflared` đang chạy. Xem mục "Khởi động lại" bên dưới.

## Cài lên điện thoại
**Android (Chrome):** mở link → menu ⋮ (góc trên phải) → **Thêm vào màn hình chính** / **Cài đặt ứng dụng**.
Hoặc: mở app → tab **Cài đặt** → nút **Cài** (nếu có).
**iPhone (Safari):** mở link → nút **Share** → **Thêm vào màn hình chính**.

Lần đầu: vào tab **Cài đặt** → bật **Thông báo đẩy** (để nhắc follow-up).

## Tính năng
- Danh sách khách: tên, SĐT, nguồn, nhu cầu (mua/thuê), khu vực, giá, diện tích.
- Trạng thái: Mới → Đã gọi → Đẹp → Đã xem nhà → Chốt / Chặn (lọc theo chip).
- Follow-up: chọn ngày-giờ, nút nhanh Hôm nay/Ngày mai/+3/+7; tab **Hôm nay** gom lịch hẹn + quá hạn.
- Nhắc lịch: thông báo khi tới hạn (khi app đang mở).
- Gọi nhanh: nút 📞 Gọi / 💬 SMS / Zalo (khi có SĐT).
- Tìm kiếm + lọc trạng thái.
- Xuất CSV (có BOM tiếng Việt, mở Excel/Sheets được) / Xuất JSON (sao lưu đầy đủ).
- Nhập lại từ CSV/JSON (khôi phục sao lưu).
- Dữ liệu lưu localStorage; **xuất file thường xuyên để sao lưu**.

## Ghi âm cuộc gọi + AI (tính năng mới)
1. **Ghi âm bằng máy**: iPhone iOS 18+ → trong cuộc gọi bấm nút **Ghi âm** (lưu trong Ghi chú, tự báo cả hai bên); hoặc dùng app ghi cuộc gọi. Lấy file `.m4a` ra (Chia sẻ → Lưu vào Files).
2. **Mở CRM** → mở khách → **🎙 Chọn file ghi âm** → chọn file.
3. Máy chạy `server.py` sẽ: chuyển giọng sang chữ (faster-whisper, model `small`) → gọi AI (Hermes) tổng hợp → trả **bản chép + tóm tắt + nhu cầu + ngân sách + bước tiếp theo**.
4. Bấm **Áp dụng vào khách** → tự điền nhu cầu/khu vực/giá/diện tích/trạng thái và ghi AI vào ghi chú. Khách có 🎙 = đã có bản chép.

Thời gian: ~50 giây cho cuộc gọi 1 phút (máy yếu, CPU). Model `small`; đổi `CRM_WHISPER_MODEL=base` nếu muốn nhanh hơn chút.

**Lưu ý:** STT dùng model cục bộ nên đôi khi sai số/ngữ cảnh (vd "quận 7" nghe thành "quận bày") — mục sai nên sửa tay. Nếu muốn chính xác hơn, thay bằng API FPT.AI/Google STT (sửa hàm `stt()` trong `server.py`).

## Giới hạn cần biết
- Nhắc lịch chỉ báo khi app đang mở (PWA local không push khi tắt). Cần nhắc khi tắt app → phải nối thêm server push (FCM).
- Link trycloudflare là link tạm; để cố định vĩnh viễn: đưa lên GitHub Pages / Cloudflare Pages.

## Khởi động lại (khi PC tắt hoặc link chết)
```bash
# 1. Server app (Flask: vừa phục vụ trang, vừa xử lý ghi âm + AI)
cd "D:/Hermes/crm-bds" && python server.py
# 2. Tunnel HTTPS (mở terminal khác)
"D:/Hermes/tools/cloudflared.exe" tunnel --url http://127.0.0.1:8080
# 3. Đọc URL mới ở dòng "Your quick Tunnel has been created!"
```

## Đóng gói lại
Thư mục `D:\Hermes\crm-bds` gồm: `index.html`, `manifest.webmanifest`, `sw.js`, `icon-192.png`, `icon-512.png`, `server.py`, `sample/`.
- Chỉ phần web (5 file đầu): đưa lên host tĩnh (GitHub Pages/Netlify/Cloudflare Pages) là chạy, nhưng **không** dùng được ghi âm + AI.
- Để dùng ghi âm + AI: phải chạy `server.py` (cần Python + ffmpeg + faster-whisper + Hermes CLI).
