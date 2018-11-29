# -- coding: utf-8 --

import pandas as pd
from WindPy import w
from datetime import date
import os
import numpy as np

class GetBenchMarkData:
    def __init__(self):
        pass

    def getdemo(self):
        aa = pd.DataFrame(np.random.random((3, 3)), index=list('abc'), columns=list('qwe'))
        writer = pd.ExcelWriter(os.getcwd() + r"\\benchData_Group%s.xlsx"%'dafsd111')
        aa.to_excel(writer)
        writer.save()

    def getMain(self,startDate='2006-01-01', endDate=date.today().strftime('%Y-%m-%d')):
        fundPoolDf = pd.read_excel('初始基金池.xlsx')
        fundCodeList = fundPoolDf['证券代码'].tolist()
        benchMarkList = [fundCode[:6]+'BI.WI' for fundCode in fundCodeList]

        w.start()
        filed = 'close'
        group = 0
        everyGrop = 10
        for benchNum in range(0, len(benchMarkList), everyGrop):
            group = group + 1
            print('获取第%s组' % str(group))
            if benchNum + everyGrop < len(benchMarkList):
                tempCodeList = benchMarkList[benchNum:benchNum + everyGrop]
            else:
                tempCodeList = benchMarkList[benchNum:]
            tempNetValue = w.wsd(codes=tempCodeList, fields=filed, beginTime=startDate, endTime=endDate,
                                 options='')
            if tempNetValue.ErrorCode != 0:
                print('wind读取基金净值数据失败，错误代码： ', tempNetValue.ErrorCode)
                continue

            benchDataDf = pd.DataFrame(tempNetValue.Data, index=tempNetValue.Codes, columns=tempNetValue.Times).T
            localpath = os.getcwd()
            writer = pd.ExcelWriter(localpath + r"\\benchData_Group%s.xlsx" % (str(group)))
            benchDataDf.to_excel(writer)
            writer.save()
        w.close()


if __name__ == '__main__':
    GetProductDataDemo = GetBenchMarkData()
    GetProductDataDemo.getMain()