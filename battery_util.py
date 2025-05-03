# 전압-잔량 테이블 (비선형 근사)
VOLTAGE_SOC_TABLE = [
    (8400, 100),
    (8000, 90),
    (7800, 80),
    (7600, 60),
    (7400, 40),
    (7200, 20),
    (7000, 10),
    (6000, 0),
]

def linear_voltage_to_percent(voltage, min_voltage=6000, max_voltage=8400):
    """선형 보간으로 전압을 잔량(%)로 변환"""
    if voltage >= max_voltage:
        return 100
    if voltage <= min_voltage:
        return 0
    return ((voltage - min_voltage) / (max_voltage - min_voltage)) * 100

def nonlinear_voltage_to_percent(voltage, table=VOLTAGE_SOC_TABLE):
    """비선형 보간으로 전압을 잔량(%)로 변환"""
    if voltage >= table[0][0]:
        return 100
    if voltage <= table[-1][0]:
        return 0
    
    # 테이블에서 인접한 두 점 찾기
    for i in range(len(table) - 1):
        v1, soc1 = table[i]
        v2, soc2 = table[i + 1]
        if v2 <= voltage <= v1:
            # 선형 보간
            return soc2 + (soc1 - soc2) * (voltage - v2) / (v1 - v2)
    return 0