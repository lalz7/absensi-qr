from flask import Blueprint, render_template, request, send_file, redirect, url_for, flash
from datetime import datetime
import pandas as pd, io
from utils import check_admin_session
from models import db, Absensi, Siswa, Pegawai, AbsensiPegawai

# Inisialisasi Blueprint dengan prefix URL
export_bp = Blueprint("export_bp", __name__, url_prefix="/export")

# ======================================================================
#  HALAMAN UTAMA EXPORT (Tidak Berubah)
# ======================================================================
@export_bp.route("/", methods=["GET", "POST"])
def export_laporan():
    auth_check = check_admin_session()
    if auth_check:
        return auth_check

    if request.method == "POST":
        tipe_data = request.form.get("tipe_data")
        jenis_laporan = request.form.get("jenis_laporan")
        format_file = request.form.get("format_file")
        tanggal = request.form.get("tanggal")
        bulan = request.form.get("bulan")
        tahun = request.form.get("tahun")

        # Redirect ke fungsi ekspor sesuai pilihan
        return redirect(url_for("export_bp.download_laporan",
                                tipe_data=tipe_data,
                                jenis_laporan=jenis_laporan,
                                format_file=format_file,
                                tanggal=tanggal,
                                bulan=bulan,
                                tahun=tahun))

    return render_template("export_laporan.html", current_year=datetime.now().year)


# ======================================================================
#  FUNGSI EKSPOR DATA (DENGAN LOGIKA BARU UNTUK STATUS)
# ======================================================================
@export_bp.route("/download_laporan")
def download_laporan():
    auth_check = check_admin_session()
    if auth_check:
        return auth_check

    tipe_data = request.args.get("tipe_data")
    jenis_laporan = request.args.get("jenis_laporan")
    format_file = request.args.get("format_file")
    tanggal = request.args.get("tanggal")
    bulan = request.args.get("bulan")
    tahun = request.args.get("tahun")

    # Query data berdasarkan tipe (siswa / pegawai)
    if tipe_data == "siswa":
        query = db.session.query(Absensi, Siswa).join(Siswa, Absensi.nis == Siswa.nis)
    else:
        # Menggunakan model AbsensiPegawai untuk data pegawai
        query = db.session.query(AbsensiPegawai, Pegawai).join(Pegawai, AbsensiPegawai.no_id == Pegawai.no_id)

    # Filter berdasarkan jenis laporan
    ModelAbsensi = Absensi if tipe_data == "siswa" else AbsensiPegawai
    if jenis_laporan == "harian" and tanggal:
        query = query.filter(ModelAbsensi.tanggal == tanggal)
    elif jenis_laporan == "bulanan" and bulan and tahun:
        query = query.filter(db.extract("month", ModelAbsensi.tanggal) == int(bulan))
        query = query.filter(db.extract("year", ModelAbsensi.tanggal) == int(tahun))

    # Susun data ke DataFrame
    data = []
    for absensi, orang in query.all():
        # ==============================================================================
        #  PERUBAHAN: Jika status "Terlambat", ubah menjadi "Hadir" untuk laporan
        # ==============================================================================
        status_laporan = "Hadir" if absensi.status == "Terlambat" else absensi.status
        # ==============================================================================

        data.append({
            "Nama": orang.nama,
            "ID": getattr(orang, "nis", getattr(orang, "no_id", None)),
            "Tanggal": absensi.tanggal.strftime("%Y-%m-%d"),
            "Waktu": absensi.waktu.strftime('%H:%M:%S'),
            "Status": status_laporan  # Gunakan status yang sudah diubah
        })

    if not data:
        flash("Tidak ada data ditemukan untuk periode tersebut.", "warning")
        return redirect(url_for("export_bp.export_laporan"))

    df = pd.DataFrame(data)
    filename = f"laporan_{tipe_data}_{jenis_laporan}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    # Ekspor ke Excel
    if format_file == "xlsx":
        output = io.BytesIO()
        with pd.ExcelWriter(output, engine="openpyxl") as writer:
            df.to_excel(writer, index=False, sheet_name="Laporan")
        output.seek(0)
        return send_file(output,
                         as_attachment=True,
                         download_name=f"{filename}.xlsx",
                         mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

    # Ekspor ke CSV
    elif format_file == "csv":
        output = io.StringIO()
        df.to_csv(output, index=False)
        output.seek(0)
        return send_file(io.BytesIO(output.getvalue().encode("utf-8")),
                         as_attachment=True,
                         download_name=f"{filename}.csv",
                         mimetype="text/csv")