from minio import Minio
client = Minio(
    endpoint="lakedpaapi-fis-mbf-dplat.apps.xplat.fis.com.vn",
    access_key="I5pnix8qE2mtXlXR",
    secret_key="hzADsWEM8DGIIQBrfjNWNNy4j0OG0cSA",
    secure=False
)

client = Minio(
    endpoint="lakedpaapi-fis-mbf-dplat.apps.xplat.fis.com.vn",
    access_key="I5pnix8qE2mtXlXR",
    secret_key="hzADsWEM8DGIIQBrfjNWNNy4j0OG0cSA",
    secure=False
)

for x in client.list_objects('youtube',recursive=True):
    print(x.object_name)

client.fget_object(bucket_name='youtube',object_name='son_tung_mtp/NƠI NÀY CÓ ANH _ TEASER MUSIC VIDEO _ SƠN TÙNG M-TP-dhviMuktFdA.mp4',file_path='test.mp3')