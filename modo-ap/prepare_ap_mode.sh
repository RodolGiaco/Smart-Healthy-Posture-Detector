#!/bin/bash

# Este script prepara el sistema para arrancar en modo Access Point (AP)
# en el próximo reinicio, simulando que es la primera vez que se enciende.

echo "🚀 Preparando el sistema para iniciar en modo AP..."

# 1. Simular estado "no configurado" eliminando el archivo de configuración.
CONFIG_FILE="/home/rodo/shpd.conf"
if [ -f "$CONFIG_FILE" ]; then
    echo "🔥 Eliminando archivo de configuración existente: $CONFIG_FILE"
    sudo rm "$CONFIG_FILE"
else
    echo "✅ El archivo de configuración no existe, no se necesita eliminar."
fi

# 2. Eliminar la bandera de hotspot activo.
HOTSPOT_FLAG="/home/rodo/.hotspot_active"
if [ -f "$HOTSPOT_FLAG" ]; then
    echo "🔥 Eliminando bandera de hotspot activo: $HOTSPOT_FLAG"
    sudo rm "$HOTSPOT_FLAG"
else
    echo "✅ La bandera de hotspot no existe, no se necesita eliminar."
fi

# 3. Limpiar configuración previa de red (eliminar IP estática de wlan0)
sudo sed -i '/^interface wlan0$/,/^$/d' /etc/dhcpcd.conf

# 4. Agregar IP estática para modo AP si no existe
if ! grep -q "interface wlan0" /etc/dhcpcd.conf; then
  echo "🔧 Configurando IP estática para wlan0 para modo AP..."
  cat <<EOF | sudo tee -a /etc/dhcpcd.conf > /dev/null
interface wlan0
    static ip_address=10.0.0.1/24
    nohook wpa_supplicant
EOF
fi

# 5. Habilitar servicios de hotspot para el arranque
sudo systemctl enable hostapd
sudo systemctl enable dnsmasq

# 6. Recargar los daemons de systemd
sudo systemctl daemon-reload

# 7. Habilitar los servicios principales para que se inicien en el arranque.
echo "✔️ Habilitando shpd-init.service..."
sudo systemctl enable shpd-init.service

echo "✔️ Habilitando setup_server.service..."
sudo systemctl enable setup_server.service

echo ""
echo "✅ ¡Listo! El sistema está configurado para iniciar en modo AP."
echo "👉 Por favor, reinicia la Raspberry Pi para aplicar los cambios con 'sudo reboot'" 