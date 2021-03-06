from datetime import datetime
from utils.separate_hours import separate_hours
import numpy as np

def setback_non_op(IAT, DAT, op_hours, HVACstat=None):
    """
    Checks to see if a location is being cooled or heated during non-operational
    hours.

    Parameters:
        - IAT: indoor air temperature, 2D array of datetime and data
        - DAT: diffuser air temperature, 2D array of datetime and data
        - HVACstat: HVAC status (optional), 2D array of datetime and data
            - 0 - off, 1 - ventilation, 3 - compressor
        - op_hours: operational hours
            - [[operational hours], [business days], [holidays]]
    Returns:
        - flag indicating whether or not this should be flagged
    """
    IAT_op, IAT_non_op = separate_hours(IAT, op_hours[0], op_hours[1],
            op_hours[2])
    DAT_op, DAT_non_op = separate_hours(DAT, op_hours[0], op_hours[1],
            op_hours[2])

    if (HVACstat):
        HVAC_op, HVAC_non_op = separate_hours(HVACstat, op_hours[0], 
                op_hours[1], op_hours[2])
    else:
        HVAC_op = None
        HVAC_non_op = None

    op_cool, op_heat, op_hvac = _grab_data(DAT_op, IAT_op, HVAC_op)
    non_cool, non_heat, non_hvac = _grab_data(DAT_non_op, IAT_non_op,
            HVAC_non_op)

    avg_DAT_c_occ = np.mean(op_cool)
    avg_DAT_h_occ = np.mean(op_heat)

    c_flag = 0
    for pt in non_cool:
        if ((pt < avg_DAT_c_occ) or (abs(pt - avg_DAT_h_occ) < 0.1)):
            c_flag += 1

    h_flag = 0
    for pt in non_heat:
        if ((pt > avg_DAT_h_occ) or (abs(pt - avg_DAT_h_occ) < 0.1)):
            h_flag += 1

    c_val = c_flag/len(DAT_non_op)
    h_val = h_flag/len(DAT_non_op)
    vent_val = non_hvac/len(DAT_non_op)

    if ((c_val + h_val + vent_val) > 0.3):
        return True

def _grab_data(DAT, IAT, HVACstat=None):
    cool_on = []
    heat_on = []
    vent_on = 0
    i = 0
    while (i < len(DAT)):
        if ((IAT[i][1] > 55) and (IAT[i][1] < 80)):
            # if DAT is less than 90% of IAT, it's cooling
            if (DAT[i][1] < (0.9 * IAT[i][1])):
                # If there's HVAC, make sure it's actually cooling
                if (HVACstat):
                    if (HVACstat[i][1] != 3):
                        continue
                cool_on.append(DAT[i][1])
            # if DAT greater than 110% IAT, then it's heating
            elif (DAT[i][1] > (1.1 * IAT[i][1])):
                # if there's HVAC status, make sure it's actually heating
                if (HVACstat):
                    if (HVAC_op[i][1] == 0):
                        continue
                heat_on.append(DAT[i][1])
            elif (HVACstat):
                if (HVACstat[i][1] == 1):
                    vent_on += 1
        i += 1
    return cool_on, heat_on, vent_on
