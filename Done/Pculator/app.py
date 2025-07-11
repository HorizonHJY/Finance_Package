# app.py
from flask import Flask
from flask_cors import CORS
import Done.Pculator.Controller.pfe_controller as controller
from flask import render_template

app = Flask(__name__)
CORS(app)

app.add_url_rule('/', view_func=controller.index)
app.add_url_rule('/get_destinations', view_func=controller.get_destinations, methods=['POST'])
app.add_url_rule('/get_commodities', view_func=controller.get_commodities, methods=['POST'])
app.add_url_rule('/get_curve_root', view_func=controller.get_curve_root, methods=['POST'])
app.add_url_rule('/get_available_months', view_func=controller.get_available_months, methods=['POST'])
app.add_url_rule('/calculate_pfe', view_func=controller.calculate_pfe, methods=['POST'])
app.add_url_rule('/export_csv',    view_func=controller.export_csv,    methods=['POST'])
app.add_url_rule('/credit_pfe_result',    view_func=controller.credit_pfe_result,methods=['POST'])


@app.errorhandler(500)
def internal_error(error):
    return render_template("500.html", error_msg=str(error)), 500

if __name__ == "__main__":
    app.run(debug=True)
    print("Available routes:")
    print(app.url_map)
