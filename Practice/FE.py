def get_vol(rsk_fac: str) -> float:
    result = viya_vol.loc[viya_vol['RISK_FACTOR'] == rsk_fac, 'VOLATILITY']
    return result.item()


a = pfe_calculator('Sell', 357.0, 0.234603017797129, 0.085555555555555)

print(a)


def pfe_calculator(direction: str, contract_price: float, contract_vol: float, time_to_exp: float) -> float:
    """
    Calculates a value based on the provided inputs, mirroring an Excel formula.

    Args:
        direction: 'Buy' or 'Sell' (string).
        contract_price: Numeric value.
        contract_vol: Numeric value.
        time_to_exp: Numeric value.

    Returns:
        The calculated result or "ERROR" if an error occurs.
    """
    buy_adjust_term = 1.645 * contract_vol * math.sqrt(time_to_exp) - 0.5 * contract_vol ** 2 * time_to_exp
    sell_adjust_term = -1.645 * contract_vol * math.sqrt(time_to_exp) - 0.5 * contract_vol ** 2 * time_to_exp

    if direction == 'Buy':
        result = contract_price * (-1 + math.exp(buy_adjust_term))
    else:  # Assumed to be "Sell" if not "Buy"
        result = contract_price * (1 - math.exp(sell_adjust_term))

    return result


def country_mapping(commodity: str) -> list:
    country_list = curve_mapping.loc[curve_mapping['Commodity'] == commodity, 'Destination']
    return list(country_list)


def risk_curve_mapping(commodity: str, destination: str) -> str:
    sub_set = curve_mapping.loc[
        (curve_mapping['Commodity'] == commodity) &
        (curve_mapping['Destination'] == destination),
        'Curve_Root'
    ]
    return sub_set.values


def commodity_mapping(destination: str) -> list:
    commodity_list = curve_mapping.loc[curve_mapping['Destination'] == destination, 'Commodity']
    return list(commodity_list)


print(risk_curve_mapping('corn', 'Portugal'))
