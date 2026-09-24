FROM python:3.11-slim

WORKDIR /app

# 1. Instalar dependencias esenciales del sistema operativo
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# 2. Configurar variables de entorno para Streamlit (Ubicación ideal antes de correr la app)
ENV STREAMLIT_SERVER_PORT=7860
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0

# 3. Copiar e instalar las librerías de Python
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 4. Copiar todo el código de la suite meteorológica
COPY . .

# 5. Abrir el puerto de comunicación
EXPOSE 7860

# Comando de arranque con protecciones de origen desactivadas para Hugging Face
CMD ["streamlit", "run", "inicio.py", "--server.enableCORS=false", "--server.enableXsrfProtection=false", "--server.enableWebsocketCompression=false"]