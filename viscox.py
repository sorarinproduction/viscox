import tkinter as tk
from tkinter import ttk
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from matplotlib.animation import FuncAnimation
import matplotlib.ticker as ticker
import matplotlib.pyplot as plt
import serial
from serial.tools import list_ports
import threading
import time
from datetime import datetime
import csv



class Application():
    def __init__(self) -> None:
        # Tkinterウィンドウの作成
        self.window = tk.Tk()
        self.window.title("Viscox - RPM and Load cell monitoring UI with COM Port Selection")

        # グラフの初期化
        self.initialize_graph()

        # UI要素の配置
        self.setup_ui_elements()

        # インスタンスの初期化
        self.ser_sensor = None
        self.ser_motor = None
        self.motor_running = False

        self.close_flag=False
        self.current_rpm = 0
        self.x_sensor_data,self.x_motor_data, self.y_sensor_data, self.y_motor_data = [], [], [],[]

        
        # グラフの更新スレッドの開始
        threading.Thread(target=self.update_canvas, args=(), daemon=False).start()

        self.window.protocol("WM_DELETE_WINDOW", self.close)

    def initialize_graph(self):
        self.fig, self.ax_sensor = plt.subplots()

        # モーターのRPM用に別軸を作成
        self.ax_motor = self.ax_sensor.twinx()
        self.line_sensor, = self.ax_sensor.plot([], [], label='Sensor data')
        self.line_motor, = self.ax_motor.plot([], [], label='Motor RPM', color='orange')

        # handlerとlabelのリストを結合
        h1, l1 = self.ax_sensor.get_legend_handles_labels()
        h2, l2 = self.ax_motor.get_legend_handles_labels()
        self.ax_sensor.legend(h1 + h2, l1 + l2, loc='upper right')

        # # モーターの軸の範囲を設定
        # self.ax_motor.set_ylim(0, 200)

        # 　軸の目盛りの単位を変更する
        self.ax_motor.yaxis.set_major_formatter(ticker.FormatStrFormatter("%drpm"))
        self.ax_sensor.yaxis.set_major_formatter(ticker.FormatStrFormatter("%.1fg"))

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.window)
        self.canvas_widget = self.canvas.get_tk_widget()
        self.canvas_widget.grid(row=0, column=2, rowspan=5, padx=10, pady=10)

    def setup_ui_elements(self):
        # COM選択用のラベルとドロップダウンリスト
        COM_frame = ttk.LabelFrame(self.window, text="COMポートを選択")
        COM_frame.grid(row=0, column=0, columnspan=2, padx=10, pady=10, sticky=tk.EW)

        # 「sensor COM」のドロップダウンリスト
        sensor_com_label = ttk.Label(COM_frame, text="センサー COM:")
        sensor_com_label.grid(row=3, column=0, padx=5, pady=5)
        self.sensor_com_combobox = ttk.Combobox(COM_frame, values=[], state="readonly")
        self.sensor_com_combobox.grid(row=3, column=1, padx=5, pady=5)

        # センサー COMポートに接続するボタン
        self.connect_sensor_button = tk.Button(COM_frame, text="センサーに接続", command=self.on_connect_sensor_button_click)
        self.connect_sensor_button.grid(row=3, column=2, pady=10)

        # 「motor COM」のドロップダウンリスト
        motor_com_label = ttk.Label(COM_frame, text="モーター COM:")
        motor_com_label.grid(row=4, column=0, padx=5, pady=5)
        self.motor_com_combobox = ttk.Combobox(COM_frame, values=[], state="readonly")
        self.motor_com_combobox.grid(row=4, column=1, padx=5, pady=5)

        # モーター COMポートに接続するボタン
        self.connect_motor_button = tk.Button(COM_frame, text="モーターに接続", command=self.on_connect_motor_button_click)
        self.connect_motor_button.grid(row=4, column=2, pady=10)

        # COMポートのリストを更新するボタン
        refresh_button = tk.Button(COM_frame, text="COMポートを更新", command=self.refresh_com_ports)
        refresh_button.grid(row=5, column=0, columnspan=2, pady=10)


        # パラメーター入力用のラベルとスピンボックス
        motor_control_frame = ttk.LabelFrame(self.window, text="パラメーターを入力")
        motor_control_frame.grid(row=1, column=0, columnspan=2, padx=10, pady=10, sticky=tk.EW)

        self.starting_rpm_label = ttk.Label(motor_control_frame, text="開始RPM:")
        self.starting_rpm_label.grid(row=0, column=0, padx=5, pady=5)
        self.starting_rpm_spinbox = ttk.Spinbox(motor_control_frame, from_=0, to=1000, increment=1)
        self.starting_rpm_spinbox.grid(row=0, column=1, padx=5, pady=5)
        self.starting_rpm_spinbox.insert(0, "10")  # 初期値

        ending_rpm_label = ttk.Label(motor_control_frame, text="終了RPM:")
        ending_rpm_label.grid(row=1, column=0, padx=5, pady=5)
        self.ending_rpm_spinbox = ttk.Spinbox(motor_control_frame, from_=0, to=1000, increment=1)
        self.ending_rpm_spinbox.grid(row=1, column=1, padx=5, pady=5)
        self.ending_rpm_spinbox.insert(0, "100")  # 初期値

        number_of_steps_label = ttk.Label(motor_control_frame, text="ステップ数:")
        number_of_steps_label.grid(row=2, column=0, padx=5, pady=5)
        self.number_of_steps_spinbox = ttk.Spinbox(motor_control_frame, from_=1, to=100, increment=1)
        self.number_of_steps_spinbox.grid(row=2, column=1, padx=5, pady=5)
        self.number_of_steps_spinbox.insert(0, "10")  # 初期値

        duration_of_one_step_label = ttk.Label(motor_control_frame, text="1ステップの持続時間（秒）:")
        duration_of_one_step_label.grid(row=3, column=0, padx=5, pady=5)
        self.duration_of_one_step_spinbox = ttk.Spinbox(motor_control_frame, from_=0.1, to=10, increment=0.1)
        self.duration_of_one_step_spinbox.grid(row=3, column=1, padx=5, pady=5)
        self.duration_of_one_step_spinbox.insert(0, "2")  # 初期値

        duration_of_interval_label = ttk.Label(motor_control_frame, text="インターバルの持続時間（秒）:")
        duration_of_interval_label.grid(row=4, column=0, padx=5, pady=5)
        self.duration_of_interval_spinbox = ttk.Spinbox(motor_control_frame, from_=0, to=10, increment=0.1)
        self.duration_of_interval_spinbox.grid(row=4, column=1, padx=5, pady=5)
        self.duration_of_interval_spinbox.insert(0, "0")  # 初期値

        start_motor_button = tk.Button(motor_control_frame, text="Start Motor", command=self.on_start_motor_button_click)
        start_motor_button.grid(row=5, column=0, padx=5, pady=5)

        stop_motor_button = tk.Button(motor_control_frame, text="Stop Motor", command=self.on_stop_motor_button_click)
        stop_motor_button.grid(row=5, column=1, padx=5, pady=10)

        # CSV保存用のフレームとエントリー
        csv_save_frame = ttk.LabelFrame(self.window, text="保存")
        csv_save_frame.grid(row=4, column=0, columnspan=2, padx=10, pady=10, sticky=tk.EW)

        file_name_label = ttk.Label(csv_save_frame, text="ファイル名:")
        file_name_label.grid(row=0, column=0, padx=5, pady=5)
        self.file_name_entry = ttk.Entry(csv_save_frame)
        self.file_name_entry.grid(row=0, column=1, padx=5, pady=5)

        csv_save_button = tk.Button(csv_save_frame, text="CSVで保存", command=self.on_csv_save_button_click)
        csv_save_button.grid(row=0, column=2, padx=5, pady=10)

        # 結果表示用のラベル
        self.result_label = tk.Label(self.window, text="",)
        self.result_label.grid(row=5, column=0, columnspan=3, sticky=tk.EW)

        
        # 初期のCOMポートリストを更新
        self.refresh_com_ports()
        self.sensor_com_combobox.current(0)
        self.motor_com_combobox.current(0)

    def update_canvas(self):
        while self.close_flag!=True:
            # 平時のサンプル数が少なすぎるので取得
            if self.ser_motor != None:
                self.correct_motor_data_snap()
            self.line_sensor.set_data(self.x_sensor_data, self.y_sensor_data)
            self.line_motor.set_data(self.x_motor_data, self.y_motor_data)
            self.ax_sensor.relim()
            self.ax_sensor.autoscale_view()
            self.ax_motor.relim()
            self.ax_motor.autoscale_view()
            self.canvas.draw()
            time.sleep(0.5)

    def correct_sensor_data(self, sensor_serial):
        while self.ser_sensor != None:
            try:
                # センサーデータの受信
                sensor_data = sensor_serial.readline().decode('utf-8').strip()

                x_sensor_value = time.time()
                y_sensor_value = float(sensor_data)

                self.x_sensor_data.append(x_sensor_value)
                self.y_sensor_data.append(y_sensor_value)

            except (AttributeError, ValueError, serial.SerialException):
                pass
            time.sleep(0.1)

    def on_connect_sensor_button_click(self):
        if self.ser_sensor != None:
            self.ser_sensor.close()
            self.ser_sensor = None
            self.connect_sensor_button.config(text="センサーに接続")
            self.sensor_com_combobox.current(0)
            self.showLog("センサーを切断しました")
            self.sensor_com_combobox.config(state="readonly")
            return

        selected_sensor_com = self.sensor_com_combobox.get()

        # "使用しない"が選択された場合、接続処理をスキップ
        if selected_sensor_com == "使用しない":
            self.showLog("Sensor COMポートが選択されていません。")
            return

        # Sensor COMポートに接続
        try:
            self.ser_sensor = serial.Serial(selected_sensor_com, 9600)  # 9600はボーレート、必要に応じて変更

            # センサー用Arduino通信スレッドの開始
            threading.Thread(target=self.correct_sensor_data, args=(self.ser_sensor,), daemon=False).start()

            self.showLog(f"Sensor COMに接続しました: {selected_sensor_com}")
            self.connect_sensor_button.config(text="センサーを切断")
            self.sensor_com_combobox.config(state="disable")
        except serial.SerialException as e:
            self.showLog(f"Sensor COMポートへの接続エラー: {e}")

    
    def set_and_sleep(self, rpm, duration):
        # モーターを回転させ、指定された時間だけ待機する関数
        if self.ser_motor!=None and self.ser_motor.is_open:
            self.current_rpm = rpm
            print(f"Set RPM to {rpm}")

            # モーターは0が書き込まれると停止するようになっている。
            if rpm != 0:
                motor_delay = 60 / (rpm * 200) * 1000000
            else:
                motor_delay = 0

            motor_delay=int(motor_delay)
            self.ser_motor.write(str(motor_delay).encode('utf-8'))

            self.correct_motor_data_snap()
            start_time = time.time()
            while time.time() - start_time < duration:
                # self.runningがFalseになったら即座に終了
                if not self.motor_running:
                    return
                time.sleep(0.1)  # 小さなウェイトで確認
            self.correct_motor_data_snap()

    def change_motor_speed(self, start_rpm, end_rpm, num_steps, step_duration, interval_duration):
        # モーターの回転数を変更する関数

        # ステップごとの回転数変化量
        rpm_change_per_step = (end_rpm - start_rpm) / num_steps

        self.correct_motor_data_snap()
        # ステップごとに実行
        for step in range(num_steps + 1):
            # 現在の回転数
            current_rpm = start_rpm + step * rpm_change_per_step

            # モーターを回転させる処理
            self.set_and_sleep(current_rpm, step_duration)

            # self.runningがFalseになったらスレッドを終了
            if not self.motor_running:
                break

            # 最後のインターバルはいらない
            if step==num_steps:
                break

            # インターバルの長さだけモーターを停止
            if interval_duration != 0:
                self.set_and_sleep(0, interval_duration)


        # モーターを停止
        self.set_and_sleep(0, 0)
        self.motor_running=False
        self.save_to_csv("自動保存")

    def start_motor_thread(self, start_rpm, end_rpm, num_steps, step_duration, interval_duration):
        # モーター制御スレッドを開始
        if self.motor_running!=True:
            self.motor_running = True
            motor_thread = threading.Thread(
                target=self.change_motor_speed,
                args=(start_rpm, end_rpm, num_steps, step_duration, interval_duration)
            )
            motor_thread.start()

    def stop_motor_thread(self):
        self.correct_motor_data_snap()
        # モーター制御スレッドを停止
        self.motor_running = False

    def correct_motor_data_snap(self):
        # 現在のRPMをy_motor_dataに追加
        x_motor_value = time.time()
        y_motor_rpm = self.current_rpm
        self.x_motor_data.append(x_motor_value)
        self.y_motor_data.append(y_motor_rpm)


    def on_connect_motor_button_click(self):
        if self.ser_motor != None:
            self.ser_motor.close()
            self.ser_motor = None
            self.stop_motor_thread()
            self.connect_motor_button.config(text="モーターに接続")
            self.showLog("モーターを切断しました")
            self.motor_com_combobox.current(0)
            self.motor_com_combobox.config(state="readonly")
            return

        selected_motor_com = self.motor_com_combobox.get()

        # "使用しない"が選択された場合、接続処理をスキップ
        if selected_motor_com == "使用しない":
            self.showLog("Motor COMポートが選択されていません。")
            return

        # Motor COMポートに接続
        try:
            self.ser_motor = serial.Serial(selected_motor_com, 9600)  # 9600はボーレート、必要に応じて変更
            self.showLog(f"Motor COMに接続しました: {selected_motor_com}")
            self.connect_motor_button.config(text="モーターを切断")
            self.motor_com_combobox.config(state="disable")
        except serial.SerialException as e:
            self.showLog(f"Motor COMポートへの接続エラー: {e}")

    def refresh_com_ports(self):
        # 利用可能なCOMポートを取得
        com_ports = [port.device for port in list_ports.comports()]
        com_ports.insert(0, "使用しない")  # "使用しない"を最初に追加
        self.sensor_com_combobox['values'] = com_ports
        self.motor_com_combobox['values'] = com_ports
        self.showLog("COMポート一覧が更新されました")

    def on_start_motor_button_click(self):
        # UIから取得したパラメーター
        start_rpm = float(self.starting_rpm_spinbox.get())
        end_rpm = float(self.ending_rpm_spinbox.get())
        steps = int(self.number_of_steps_spinbox.get())
        step_length = float(self.duration_of_one_step_spinbox.get())
        interval_length = float(self.duration_of_interval_spinbox.get())

        # モーター制御スレッドを開始
        if self.ser_motor != None:
            self.start_motor_thread(start_rpm, end_rpm, steps, step_length, interval_length)
        else:
            self.showLog("モーターが選択されていません")

    def on_stop_motor_button_click(self):
        # モーター制御スレッドを停止
        if self.ser_motor != None:
            self.stop_motor_thread()
        else:
            self.showLog("モーターが選択されていません")

    def on_csv_save_button_click(self):
        file_name = self.file_name_entry.get()
        if not file_name:
            self.showLog("ファイル名を入力してください。")
            return
        self.save_to_csv(file_name)

    def save_to_csv(self, file_name):

        # ファイル名に日時を付加
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_name_with_timestamp = f"{timestamp}_{file_name}.csv"

        # CSVファイルにデータを保存
        with open(file_name_with_timestamp, mode='w', newline='') as file:
            writer = csv.writer(file)
            writer.writerow(["Time", "Sensor Data"])  # ヘッダーを書き込む
            writer.writerows(zip(self.x_sensor_data, self.y_sensor_data))  # データを書き込む
            writer.writerow(["Time", "Motor Data"])  # ヘッダーを書き込む
            writer.writerows(zip(self.x_motor_data, self.y_motor_data))  # データを書き込む

        self.showLog(f"データを {file_name_with_timestamp} に保存しました.")

    def showLog(self, message: str):
        self.result_label.config(text=message)

    def run(self):
        try:
            # COMポートリストを更新
            self.refresh_com_ports()
            # Tkinterメインループ
            self.window.mainloop()
        except KeyboardInterrupt:
            self.close()

    def close(self):
        self.close_flag=True

        if self.ser_motor != None:
            self.stop_motor_thread()
        if self.ser_sensor != None:
            self.ser_sensor.close()
        if self.ser_motor != None:
            self.ser_motor.close()

        self.window.destroy()
        self.window.quit()



if __name__ == "__main__":
    app = Application()
    app.run()
