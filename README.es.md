# freecam-a12

Libera la **mini cámara Wi-Fi "A12"** (Linklemo / XC Things) de la nube del fabricante.
Tus imágenes se quedan en tu red. Sin cuenta, sin app y sin servidores en otro país.

> 🇬🇧 [Read in English](README.md)

## Estado

🚧 **Investigación inicial.** Todavía no hay nada listo para el usuario final.

✅ **2026-10-27:** primera foto obtenida totalmente offline (sin app, sin cuenta y sin internet). Por dentro la A12
es una **HA10** y habla el mismo protocolo PPRPC que las cámaras INO-A9. Detalles en
[docs/findings.md](docs/findings.md).

✅ **2026-10-27:** conectada al Wi-Fi de casa sin la app ([`tools/setup_wifi.ps1`](tools/setup_wifi.ps1)) y con
vídeo en directo por la red local.

## ¿Es mi cámara?

| Pista | Valor |
|---|---|
| App del fabricante | **Linklemo** (`com.xcthings.fchan`) |
| Wi-Fi de configuración (modo AP) | El SSID empieza por **`LLM_`** |
| SoC probable | Beken **BK7252N** (por confirmar, ver [docs/hardware.md](docs/hardware.md)) |
| Protocolo probable | **PPRPC** de XC Things en el puerto TCP/UDP **20190** |

Si tu cámara usa la app **V720 / Naxclow** (puerto 6123) o **HDWiFiCam Pro / YsxLite** (PPPP), es de otra
familia. Mira los [proyectos relacionados](README.md#related-projects).

## Objetivos

1. **Identificar** el hardware y confirmar a qué familia de protocolo pertenece la A12.
2. **Streaming local ya:** documentar cómo usar la cámara totalmente offline (VLAN aislada, internet bloqueado)
   con los clientes libres que ya existen, y enviarles mejoras cuando haga falta.
3. **Firmware sin nube, más adelante:** estudiar el firmware del BK7252N y avanzar hacia un reemplazo que nunca
   contacte con el exterior y ofrezca un stream estándar (MJPEG/RTSP). Ningún firmware libre soporta todavía la
   cámara en este chip.

## Uso responsable

Úsalo solo con dispositivos **tuyos**. Este proyecto no incluye firmware ni claves del fabricante.

## Licencia

[MIT](LICENSE)
