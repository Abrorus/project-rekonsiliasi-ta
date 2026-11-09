"""Prapemrosesan halaman scan/foto (BNI, Mandiri) dengan OpenCV.

Tujuan: teks hitam tetap gelap, latar berwarna (hijau-kuning, moire, bayangan) menjadi terang rata.
"""
import cv2
import numpy as np


def render_pages(pdf_path, dpi=200):
    """PDF -> daftar gambar BGR (satu per halaman). Perlu Poppler untuk pdf2image."""
    from pdf2image import convert_from_path
    return [cv2.cvtColor(np.array(p), cv2.COLOR_RGB2BGR) for p in convert_from_path(pdf_path, dpi=dpi)]


def normalisasi(img_bgr):
    """Saluran maksimum (latar berwarna jadi terang, teks hitam tetap gelap) lalu
    pembagian terhadap estimasi latar (meratakan bayangan/pencahayaan). Hasil: uint8 gray."""
    g = img_bgr.max(axis=2)
    kecil = cv2.resize(g, None, fx=0.125, fy=0.125, interpolation=cv2.INTER_AREA)
    bg = cv2.medianBlur(kecil, 31)
    bg = cv2.resize(bg, (g.shape[1], g.shape[0]), interpolation=cv2.INTER_LINEAR)
    return cv2.divide(g, np.maximum(bg, 1), scale=255)


def estimasi_miring(gray, rentang=3.0, langkah=0.25):
    """Sudut kemiringan (derajat) dengan memaksimalkan variansi proyeksi horizontal."""
    kecil = cv2.resize(gray, None, fx=0.25, fy=0.25, interpolation=cv2.INTER_AREA)
    biner = (cv2.threshold(kecil, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU)[1] > 0).astype(np.float32)
    h, w = biner.shape
    terbaik, skor_terbaik = 0.0, -1.0
    for a in np.arange(-rentang, rentang + 1e-6, langkah):
        m = cv2.getRotationMatrix2D((w / 2, h / 2), a, 1.0)
        r = cv2.warpAffine(biner, m, (w, h), flags=cv2.INTER_NEAREST)
        skor = float(np.var(r.sum(axis=1)))
        if skor > skor_terbaik:
            terbaik, skor_terbaik = a, skor
    return terbaik


def luruskan(gray, img_bgr=None, ambang=0.3):
    """Putar balik bila kemiringan > ambang derajat. Mengembalikan (gray, img_bgr, sudut)."""
    a = estimasi_miring(gray)
    if abs(a) <= ambang:
        return gray, img_bgr, 0.0
    h, w = gray.shape
    m = cv2.getRotationMatrix2D((w / 2, h / 2), a, 1.0)
    g2 = cv2.warpAffine(gray, m, (w, h), flags=cv2.INTER_CUBIC, borderValue=255)
    i2 = None if img_bgr is None else cv2.warpAffine(img_bgr, m, (w, h), flags=cv2.INTER_CUBIC,
                                                      borderValue=(255, 255, 255))
    return g2, i2, a


def siapkan_halaman(img_bgr):
    """Pipeline prapemrosesan satu halaman -> (gray_normal, img_bgr_terluruskan, sudut)."""
    n = normalisasi(img_bgr)
    return luruskan(n, img_bgr)