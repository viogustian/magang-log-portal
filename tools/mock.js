/* Perilaku TIRUAN untuk halaman uji. Bukan kode portal asli.
 *
 * Markup halaman berasal dari snapshot asli (lihat make_fixture.py); skrip ini hanya menambah
 * perilaku minimum agar adapter Playwright bisa diuji tanpa menyentuh portal:
 *  - klik hari "Belum Diisi" yang aktif  => panel form terbuka untuk tanggal itu
 *  - lokasi dari navigator.geolocation    => kotak "Lokasi berhasil diakses" / "tidak dapat diakses"
 *  - tombol "Simpan dan Kirim" aktif bila 3 kolom >= 100 karakter + pernyataan dicentang + lokasi ok
 *  - klik kirim => status hari menjadi "Menunggu Persetujuan" (disimpan di localStorage agar
 *    bertahan saat muat ulang, meniru penyimpanan di server)
 * Parameter query: ?fail=nosave (kirim "berhasil" tetapi tidak tersimpan), ?preopen=0 (panel
 * tidak terbuka saat halaman dimuat).
 * ASUMSI (tidak ada di snapshot): aturan aktif/nonaktif tombol kirim, teks galat lokasi,
 * ada/tidaknya dialog konfirmasi. Semuanya perlu dicocokkan dengan portal asli.
 */
(function () {
  "use strict";
  var q = new URLSearchParams(location.search);
  var failMode = q.get("fail");
  var MIN = 100;
  var DOT = "·";

  var panel = document.querySelector("section.daily-panel");
  var form = panel.querySelector("form.daily-form");
  var h2 = panel.querySelector("h2");
  var locBox = form.querySelector(".location-permission");
  var areas = form.querySelectorAll("textarea");
  var cb = form.querySelector("input[type=checkbox]");
  var save = Array.prototype.find.call(form.querySelectorAll("button"), function (b) {
    return b.textContent.indexOf("Simpan dan Kirim") >= 0;
  });
  var dayButtons = document.querySelectorAll("button.calendar-day-button");
  var current = null;
  var locOK = false;

  function parseLabel(btn) {
    var m = /,\s*(\d+) (\S+) (\d{4}),\s*(.+)$/.exec(btn.getAttribute("aria-label"));
    return { d: m[1], mon: m[2], y: m[3], status: m[4], key: m[3] + "-" + m[2] + "-" + m[1] };
  }

  function setStatus(btn, status) {
    btn.setAttribute("aria-label", btn.getAttribute("aria-label").replace(/,\s*[^,]+$/, ", " + status));
  }

  function store(key, value) {
    try { localStorage.setItem("mock-status:" + key, value); } catch (e) { /* abaikan */ }
  }

  function stored(key) {
    try { return localStorage.getItem("mock-status:" + key); } catch (e) { return null; }
  }

  function update() {
    var ok = true;
    Array.prototype.forEach.call(areas, function (t) {
      if (t.value.trim().length < MIN) { ok = false; }
    });
    var enabled = ok && cb.checked && locOK;
    save.disabled = !enabled;
    save.classList.toggle("v-btn--disabled", !enabled);
  }

  function showLoc(ok) {
    locOK = ok;
    locBox.innerHTML = ok
      ? "<div><strong>Lokasi berhasil diakses</strong><p>Koordinat ditemukan.</p></div>"
      : "<div><strong>Lokasi tidak dapat diakses</strong><p>Izinkan akses lokasi pada browser.</p></div>";
    update();
  }

  function requestLocation() {
    locOK = false;
    locBox.innerHTML = "<div><strong>Meminta lokasi</strong></div>";
    update();
    if (!navigator.geolocation) { showLoc(false); return; }
    navigator.geolocation.getCurrentPosition(
      function () { showLoc(true); },
      function () { showLoc(false); },
      { timeout: 4000 }
    );
  }

  function openFor(btn) {
    current = btn;
    var p = parseLabel(btn);
    var canFill = p.status === "Belum Diisi" && !btn.disabled;
    panel.hidden = !canFill;
    if (!canFill) { return; }
    h2.textContent = "Tambah laporan " + DOT + " " + p.d + " " + p.mon + " " + p.y;
    Array.prototype.forEach.call(areas, function (t) { t.value = ""; });
    cb.checked = false;
    requestLocation();
  }

  // status yang "tersimpan di server" (localStorage) diterapkan ke kalender
  Array.prototype.forEach.call(dayButtons, function (b) {
    var s = stored(parseLabel(b).key);
    if (s) { setStatus(b, s); }
    b.addEventListener("click", function () { openFor(b); });
  });
  Array.prototype.forEach.call(areas, function (t) { t.addEventListener("input", update); });
  cb.addEventListener("change", update);

  save.addEventListener("click", function () {
    setTimeout(function () {
      if (failMode !== "nosave" && current) {
        store(parseLabel(current).key, "Menunggu Persetujuan");
        setStatus(current, "Menunggu Persetujuan");
      }
      panel.hidden = true;
    }, 200);
  });

  var today = document.querySelector("button.calendar-day-button[aria-current=date]");
  if (q.get("preopen") !== "0" && today) { openFor(today); } else { panel.hidden = true; }
})();
