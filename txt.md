# Redes_Ruteo
## Pasos:
cd a la carpeta principal
docker compose -d up
python -m venv .venv
source .venv/Scripts/activate #windows
pip install requirements.txt
python -c "import psycopg2; print('psycopg2 ok')"
cd scripts
chmod +x run_all_etl_parallel.sh
./run_all_etl_parallel.sh