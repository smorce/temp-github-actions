import os, sys, json, requests
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import pickle
# 実行上問題ないwarningは非表示にする
import warnings
warnings.filterwarnings('ignore')

from google.cloud import bigquery

pd.set_option('display.max_rows', 500)
pd.set_option('display.max_columns', 500)

# setting variables
user = "smorce"
repo = "temp-github-actions"
event_type = "delivery-retrain-model"
Personal_Access_TOKEN = os.environ.get("TOKEN")


def load_model():
    filepath = "./models/GaussianProcessRegressor.pkl"
    _model = pickle.load(open(filepath,'rb'))
    return _model


def load_data():
    # **予測するためBigQueryからユーザのログデータをロードする**
    bqclient = bigquery.Client()
    print("!----- BigQueryから予測用のデータを読み込みます -----!")
    # Download query results.
    # ===================================================
    # 最新のデータをロードして df に保存する(一応、1,000件に絞る)
    # ===================================================
    query_string = """
    SELECT
        y
        ,f1,f2,f3,f4,f5,f6,f7,f8,f9,f10
        ,t1.time
        ,noise
    FROM
        df_on_missing_value_completion.df_on_missing_value_completion AS t1
    INNER JOIN
        (SELECT MAX(time) AS maxDate FROM df_on_missing_value_completion.df_on_missing_value_completion) AS t2
    ON
        t1.time = t2.maxDate
    LIMIT
        1000
    """
    _df = (
        bqclient.query(query_string)
        .result()
        .to_dataframe(
            # Optionally, explicitly request to use the BigQuery Storage API. As of
            # google-cloud-bigquery version 1.26.0 and above, the BigQuery Storage
            # create_bqstorage_client はデフォルトで True
            # BigQuery Storage APIは、BigQueryから行をフェッチするためのより高速な方法で、True で使用する
            # https://googleapis.dev/python/bigquery/latest/generated/google.cloud.bigquery.job.QueryJob.html
            create_bqstorage_client=True,
        )
    )
    # 予測時の日付データは消さない。どのタイミングのデータを使って予測したのかを記録する
    # del df['time']

    # **予測したデータもロードする**
    # 欲しいのは最新の日付だけ(last_prediction)
    # query_string = """
    # SELECT
    #     MAX(time) AS last_prediction
    # FROM
    #     df_on_missing_value_completion.predicted_df_on_missing_value_completion
    # """
    # predicted = (
    #             bqclient.query(query_string)
    #             .result()
    #             .to_dataframe(
    #                 # Optionally, explicitly request to use the BigQuery Storage API. As of
    #                 # google-cloud-bigquery version 1.26.0 and above, the BigQuery Storage
    #                 # create_bqstorage_client はデフォルトで True
    #                 # BigQuery Storage APIは、BigQueryから行をフェッチするためのより高速な方法で、True で使用する
    #                 # https://googleapis.dev/python/bigquery/latest/generated/google.cloud.bigquery.job.QueryJob.html
    #                 create_bqstorage_client=True,
    #     )
    # )
    # last_prediction_date = predicted['last_prediction']
    print("!----- BigQueryから予測用のデータを読み込みました -----!")
    return _df



# モデルのロード
model = load_model()

# 予測に必要なデータをBigQueryから読み込む
df = load_data()

noise = df.noise.max()
print()
print('今回の noise =', noise)
del df['noise']


# **推論する**

# 予測に必要な平均値と標準偏差を読み込む
filename = "./data/mean_and_std.txt"
_dict = pickle.load(open(filename, 'rb'))


# 学習で使ったデータを読み込む(使わない。ドリフトチェックで使うかも)
# filename = "./data/training.csv"
# training = pd.read_csv(filename)
# 学習時の最新の日付
# last_training_date = training.time.max()


# -----------------------------------
# y を予測する
# -----------------------------------
# セッティング
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import WhiteKernel, RBF, ConstantKernel, Matern, DotProduct

# dataset(array型)
# y = df.y.values
x = df.drop(columns=['y','time']).values

# autoscaling(標準化)
autoscaled_x = (x - x.mean(axis=0)) / x.std(axis=0, ddof=1)
# autoscaled_y = (y - y.mean()) / y.std(ddof=1)

# 標準化しているので、標準化したときの計算の逆をやることで割り戻している。標準偏差の方は y_train の標準偏差をかけるだけで散らばり具合が戻せる
predicted_y_test, predicted_y_test_std = model.predict(autoscaled_x, return_std=True)
predicted_y_test = predicted_y_test * _dict['y_std'] + _dict['y_mean']
predicted_y_test_std = predicted_y_test_std * _dict['y_std']

# 結果を格納
mean_result = predicted_y_test
std_result = predicted_y_test_std

# ------------------------------------------------------
### ドリフトチェック ###
# ------------------------------------------------------
# 予測した結果 mean_result と、学習時の3σの"平均値"を比較して異常値が出ていたら
# データの分布が変わったとみなして再学習する
# <分岐>ドリフトチェックに引っかかる
#   YES → モデルを再学習して強制的にスクリプトを終了させる。予測する意味がないので、BigQuery の更新も行わない
#    NO → 通常通りの処理を最後まで実行する

# 注意点
# どうやっても多くの異常値を発生させることができなかったので、代表値をイジって無理やり異常値を大量発生させる
#   noise = 200 なら → mean_uper * 0.8, mean_under * 0.8
# ------------------------------------------------------
# 学習時の信頼区間を再現
# uper, under <class 'numpy.ndarray'>
uper = _dict['predicted_y_test'] + 3.00 * _dict['predicted_y_test_std']
under = _dict['predicted_y_test'] - 3.00 * _dict['predicted_y_test_std']

# 比較するための代表値が必要なので平均値とする
mean_uper = uper.mean()
mean_under = under.mean()

# noise = 200 なら
if noise == 200:
    mean_uper *= 0.8
    mean_under *= 0.8

# mean_uper を超えるもの もしくは mean_under を下回るものが全部で 10% 以上か？
N = 0.1
uper_count = np.count_nonzero(mean_result > mean_uper)  # mean_uper を超えた件数
under_count = np.count_nonzero(mean_result < mean_under)  # mean_uper を下回った件数
out_count = uper_count + under_count

print('異常値の件数 =', out_count)
print('異常値の割合 =', out_count / len(mean_result))

if ( out_count / len(mean_result) ) >= N:
    url = f'https://api.github.com/repos/{user}/{repo}/dispatches'
    resp = requests.post(url, headers={'Authorization': f'token {Personal_Access_TOKEN}'}, data = json.dumps({'event_type': event_type}))
    print("10% 以上の異常を検知したので、モデルの再学習用ワークフローを GitHub Actions で実行します。BigQuery は更新せずに予測を強制終了します")
    # モデルの再学習用ワークフローを発火させたら predict スクリプトは強制終了
    sys.exit(0)


# 異常値が何もなければ下記の処理に続く
print("10% 以上の異常を検知しなかったので通常の predict-flow を実行します")


# **グラフ描画と保存**
index = df.index

plt.rcParams['font.size'] = 12  # 横軸や縦軸の名前の文字などのフォントのサイズ

plt.figure(figsize=(10, 5))
plt.plot(index, mean_result, color='navy', label='Predicted Mean')
plt.fill_between(index, mean_result-3.00*std_result, mean_result+3.00*std_result, color='navy', alpha=0.2, label='Predicted Boundaries - 3sigma')
plt.xlabel('Index Datapoint')
plt.ylabel('Predicted Mean')
plt.legend()

plt.savefig("./artifact/Predicted_Mean.png", dpi=100, bbox_inches="tight")
plt.clf() # plt.clf() → plt.close() でメモリ解放
plt.close('all')


# **入力データと予測結果をBigQueryに書き込む**
# pandas.to_gbq のやり方しか見つからなかった

# df に予測値を入れる
df['GPR_Mean_Predicted'] = mean_result
df['GPR_Upper_Boundary_on3sigma']= mean_result+3.00*std_result
df['GPR_Lower_Boundary_on3sigma']= mean_result-3.00*std_result


outlier = []

for i in range(len(df)):
    o = "Non Outlier"
    if df['y'].loc[i]<=df['GPR_Upper_Boundary_on3sigma'].loc[i] and df['y'].loc[i]>=df['GPR_Lower_Boundary_on3sigma'].loc[i]:
        True
    else:
        o="Outlier"
    outlier.append(o)

df['Outlier']=outlier

outlier_spec = []

for i in range(len(df)):
    o = "Non Outlier"
    if df['y'].loc[i]>=df['GPR_Upper_Boundary_on3sigma'].loc[i]:
        o = "Upper Outlier"
    if df['y'].loc[i]<=df['GPR_Lower_Boundary_on3sigma'].loc[i]:
        o = "Lower Outlier"
    else:
        True
    outlier_spec.append(o)

df['Outlier_Type'] = outlier_spec

# if_exists="replace" : 同じものがあったら上書き保存する
df.to_gbq("df_on_missing_value_completion.predicted_df_on_missing_value_completion", if_exists="replace")


