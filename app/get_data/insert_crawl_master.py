import pandas as pd
import numpy as np
import psycopg2
from psycopg2.extras import DictCursor
from minio import Minio

conn = psycopg2.connect(user="dpacrawler",
                        password="123456a@",
                        host="127.0.0.1",
                        port="5432",
                        database="dpacrawlconf")


client = Minio(
    endpoint="lakedpaapi-fis-mbf-dplat.apps.xplat.fis.com.vn",
    access_key="I5pnix8qE2mtXlXR",
    secret_key="hzADsWEM8DGIIQBrfjNWNNy4j0OG0cSA",
    secure=False
)

def insert_into_detail_crawl():
    global client
    global conn
    cur = conn.cursor()
    query = """
        INSERT INTO 
            detail_crawl (crawl_master_id,name,path,item_type,status)
        VALUES
        (%s,%s,%s,%s,%s)
    """
    list_path = []
    for x in client.list_objects('youtube',recursive=True):
        full_path = x.object_name
        list_path.append([full_path.split('/')[1],full_path])
    
    crawl_master_id = 1
    item_type = "org_song"
    status = 0
    for id,item in enumerate(list_path,start=1):
        cur.execute(query,(crawl_master_id,item[0],item[1],item_type,status))
    conn.commit()
    conn.close()

insert_into_detail_crawl()