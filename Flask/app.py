# app.py
from flask import Flask
from flask_cors import CORS
import Flask.Controller.pfe_controller as controller

app = Flask(__name__)
CORS(app)

# 显式绑定路由到函数
app.add_url_rule('/', view_func=controller.index)
app.add_url_rule('/get_destinations', view_func=controller.get_destinations, methods=['POST'])
app.add_url_rule('/get_commodities', view_func=controller.get_commodities, methods=['POST'])
app.add_url_rule('/get_curve_root', view_func=controller.get_curve_root, methods=['POST'])
app.add_url_rule('/get_available_months', view_func=controller.get_available_months, methods=['GET'])
app.add_url_rule('/calculate_pfe', view_func=controller.calculate_pfe, methods=['POST'])
app.add_url_rule('/export_csv',    view_func=controller.export_csv,    methods=['POST'])
if __name__ == "__main__":
    app.run(debug=True)
    print("Available routes:")
    print(app.url_map)
