import pandas as pd
from datetime import datetime
from dateutil.relativedelta import relativedelta

month_code_map = {
    'Jan': 'F', 'Feb': 'G', 'Mar': 'H', 'Apr': 'J', 'May': 'K', 'Jun': 'M',
    'Jul': 'N', 'Aug': 'Q', 'Sep': 'U', 'Oct': 'V', 'Nov': 'X', 'Dec': 'Z'
}

def date_transfer(start_date,num_months):
    results = []
    for i in range(num_months):
        target_date = start_date + relativedelta(months=i)
        # 得到月末
        eomonth = (target_date.replace(day=1) + relativedelta(months=1)) - relativedelta(days=1)
        month_str = target_date.strftime('%b-%y')  # eg: Apr-25
        short_month = month_code_map[target_date.strftime('%b')] + target_date.strftime('%y')  # eg: J25
        date_in_number = (eomonth - datetime(1899, 12, 30)).days  # Excel serial date

        results.append({
            'month-str': month_str,
            'ShortMonth': short_month,
            'date in number': date_in_number
        })

    print(pd.DataFrame(results))


def replace_space_with_underscore(text):
    return text.replace(' ', '_')


