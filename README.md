# Portfolio Bayu

## Live chat

Pengunjung dapat mengirim pesan dari widget di halaman portfolio. Pesan tersimpan di SQLite pada `instance/chat.sqlite3` (atau lokasi `CHAT_DATABASE`) dan dapat dibalas dari `/operator`.

Konfigurasikan kredensial operator dan secret Flask sebelum menjalankan aplikasi. Gunakan password operator yang kuat dan secret acak yang berbeda untuk tiap deployment.

PowerShell:

```powershell
$env:FLASK_SECRET_KEY = python -c "import secrets; print(secrets.token_hex(32))"
$env:CHAT_OPERATOR_USERNAME = "nama-operator"
$env:CHAT_OPERATOR_PASSWORD = "password-kuat"
$env:SESSION_COOKIE_SECURE = "1"
python app.py
```

Set `SESSION_COOKIE_SECURE=1` when serving the site over HTTPS. Leave it unset for local HTTP development.

For a Linux production deployment using Gunicorn and WebSockets:

```sh
gunicorn --worker-class gthread --threads 100 --workers 1 app:app
```

Jalankan satu worker Gunicorn karena Socket.IO dan sesi operator menggunakan memori proses. Simpan SQLite pada disk persisten, bukan filesystem sementara. Halaman operator memakai sesi Flask bertanda tangan; pastikan `FLASK_SECRET_KEY` disimpan sebagai secret di environment deployment. Browser memuat Socket.IO client versi tetap dari CDN.

### Deploy ke Render

File `render.yaml` menyiapkan web service, environment variables, dan persistent disk untuk database chat. Di dashboard Render pilih **New > Blueprint**, hubungkan repository ini, lalu isi `CHAT_OPERATOR_USERNAME` dan `CHAT_OPERATOR_PASSWORD` ketika diminta. Setelah deploy selesai, buka URL Render yang diberikan dan tambahkan `/operator/login` untuk masuk sebagai operator.

Persistent disk diperlukan agar riwayat chat tidak hilang saat service restart. Konfigurasi ini menggunakan plan `starter` karena persistent disk dan live chat membutuhkan service yang tetap berjalan.

Tes:

```powershell
python -m unittest discover -s tests
```
