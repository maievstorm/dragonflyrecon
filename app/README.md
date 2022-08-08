uvicorn service:app --reload
python main.py --hash 1
python main.py --recognize 1 --is_save 1 --fast_check 0

# pip
pip install -r requirements.txt

# conda
conda install -c conda-forge requirements_conda.txt