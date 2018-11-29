# -- coding: utf-8 --

'''
    获取基金池和指数的具体数据
    数据来源：本地excel，wind,同花顺ifind
'''

import pandas as pd
from iFinDPy import *
from WindPy import w
from datetime import date
import numpy as np
from PrintInfo import PrintInfo
import os


class GetFundPool:
    def __init__(self):
        self.PrintInfoDemo = PrintInfo()

    def getDataLocal(self,CodeList=[],dataFlag='Fund',method='NotBench'):
        '''
        从本地读取基金历史数据
        :param CodeList: 代码列表
        :return: 要读取的历史基金数据
        '''
        resultDf = pd.DataFrame()
        localPath = r"C:\\Users\\lenovo\\PycharmProjects\\FundPoolSelect\\GetDataSource\\HistoryData\\"
        if dataFlag == 'Fund':
            localPath = localPath +r"FundNetValueDf\\"
            totalExcelNameList = os.listdir(localPath)
            if not totalExcelNameList:
                self.PrintInfoDemo.PrintLog('本地文件中未找到历史%s数据！'%dataFlag)
                return resultDf

            dfList = []
            for excelName in totalExcelNameList:
                tempDf = pd.read_excel(localPath+excelName)
                dfList.append(tempDf)
            totalNetValueDf = pd.concat(dfList,axis=1,join='inner')

            targetList = list(set(totalNetValueDf.columns.tolist()).intersection(set(CodeList)))
            self.PrintInfoDemo.PrintLog('本地文件有数量：%s' % str(totalNetValueDf.shape[1]))
            self.PrintInfoDemo.PrintLog('目标数量：%s' % str(len(targetList)))
            resultDf = totalNetValueDf[targetList]
            return resultDf
        elif dataFlag=='Index':
            if method=='NotBench':
                localPath = localPath+"IndexValueDf.xlsx"
                try:
                    resultDf = pd.read_excel(localPath)
                except:
                    self.PrintInfoDemo.PrintLog('未读取到本地指数历史数据，请检查！')
                return resultDf
            else:
                localPath = localPath + r"benchMarkData\\"
                totalExcelNameList = os.listdir(localPath)
                if not totalExcelNameList:
                    self.PrintInfoDemo.PrintLog('本地文件中未找到历史%s数据！' % dataFlag)
                    return resultDf

                dfList = []
                for excelName in totalExcelNameList:
                    tempDf = pd.read_excel(localPath + excelName)
                    dfList.append(tempDf)
                totalIndexValueDf = pd.concat(dfList, axis=1, join='outer')
                return totalIndexValueDf

        elif dataFlag=='InitFund':
            '''
                初始基金池，考虑量化账号数据请求限制问题，该部分暂由wind终端中手动“基金筛选”,后续可维护全市场程序筛选
                目前筛选逻辑（保存在wind基金筛选—>我的方案）：（1）成立年限<=2013-11-19；（2）基金规模>=6亿元
            '''
            localPath = localPath + "初始基金池.xlsx"
            resultDf = pd.read_excel(localPath)
            return resultDf
        elif dataFlag == 'InitIndex':
            localPath = localPath + "初始指数池.xlsx"
            resultDf = pd.read_excel(localPath)
            return resultDf

    def getFundNetData(self, fundCodeList=[], startDate='2006-01-01', endDate=date.today().strftime('%Y-%m-%d'),SourceFlag='Wind'):
        '''
            获取基金历史净值数据，ifind或wind
        :return:DataFrame
        '''

        if not fundCodeList:
            self.PrintInfoDemo.PrintLog('获取的目标基金代码列表为空，请检查！')
            return pd.DataFrame()

        netValueDf = self.getDataLocal(CodeList=fundCodeList,dataFlag='Fund')
        if not netValueDf.empty:
            return netValueDf

        everyGrop = 10
        if SourceFlag=='Wind':
            w.start()
            filed = 'NAV_adj'  # 复权单位净值

            group = 0
            dfList = []
            for fundNum in range(0,len(fundCodeList),everyGrop):
                group = group + 1
                self.PrintInfoDemo.PrintLog('获取第%s组'%str(group))
                if fundNum + everyGrop<len(fundCodeList):
                    tempCodeList = fundCodeList[fundNum:fundNum+everyGrop]
                else:
                    tempCodeList = fundCodeList[fundNum:]
                tempNetValue = w.wsd(codes=tempCodeList, fields=filed, beginTime=startDate, endTime=endDate,options='Fill=Previous')
                if tempNetValue.ErrorCode != 0:
                    self.PrintInfoDemo.PrintLog(infostr='wind读取基金净值数据失败，错误代码： ', otherInfo=tempNetValue.ErrorCode)
                    return pd.DataFrame()

                tempNetValueDf = pd.DataFrame(tempNetValue.Data, index=tempNetValue.Codes, columns=tempNetValue.Times).T
                writer = pd.ExcelWriter(
                    r"C:\\Users\\lenovo\\PycharmProjects\\FundPoolSelect\\GetDataSource\\FundNetValueDF\\"+"复权单位净值_Group%s.xlsx"%(str(group)))
                tempNetValueDf.to_excel(writer)
                writer.save()
                dfList.append(tempNetValueDf)
            w.close()
            netValueDf = pd.concat(dfList,axis=1,join='outer')
            return netValueDf
        else:
            thsLogin = THS_iFinDLogin("zszq5072", "754628")
            if thsLogin not in [0, -201]:
                self.PrintInfoDemo.PrintLog('登录ifind失败，请检查！')
                return pd.DataFrame()

            group = 0
            dfNetList = []
            for fundNum in range(0, len(fundCodeList), everyGrop):
                group = group + 1
                self.PrintInfoDemo.PrintLog('获取第%s组' % str(group))
                if fundNum + everyGrop < len(fundCodeList):
                    tempCodeList = fundCodeList[fundNum:fundNum + everyGrop]
                else:
                    tempCodeList = fundCodeList[fundNum:]

                codeListStr = ','.join(tempCodeList)

                indicators = 'adjustedNAV'
                params = 'Interval:D,CPS:1,baseDate:1900-01-01,Currency:YSHB,fill:Previous'
                data = THS_HistoryQuotes(codeListStr, indicators, params, startDate, endDate)

                if data['errorcode'] != 0:
                    self.PrintInfoDemo.PrintLog(infostr='ifind获取指数数据失败，错误代码： ', otherInfo=data['errorcode'])
                    return pd.DataFrame()
                tData = THS_Trans2DataFrame(data)
                dfListIn = []
                for code, tempdf in tData.groupby(by=['thscode']):
                    tempdf.set_index('time', drop=True, inplace=True)
                    tempFianlDf = tempdf.rename(columns={indicators: code}).drop(labels=['thscode'], axis=1)
                    dfListIn.append(tempFianlDf)
                tempNetValueDf = pd.concat(dfListIn, axis=1, join='outer')
                writer = pd.ExcelWriter(
                    r"C:\\Users\\lenovo\\PycharmProjects\\FundPoolSelect\\GetDataSource\\HistoryData\\FundNetValueDF\\" + "复权单位净值_Group%s.xlsx" % (
                        str(group)))
                tempNetValueDf.to_excel(writer)
                writer.save()
                dfNetList.append(tempNetValueDf)
            thsLogout = THS_iFinDLogout()
            netValueDf = pd.concat(dfNetList, axis=1, join='outer')
            return netValueDf

    def getIndexData(self,indexCodeList=[],startDate='2006-01-01', endDate=date.today().strftime('%Y-%m-%d'),SourceFlag='Wind',method='NotBench'):
        '''
        获取指数历史数据
        :param indexCodeList: 指数代码列表
        :param startDate: 指数开始时间
        :param endDate: 指数截止时间
        :param SourceFlag: 获取数据的来源标签
        :return: DataFrame
        '''

        if not indexCodeList:
            self.PrintInfoDemo.PrintLog('获取的目标指数代码列表为空，请检查！')
            return pd.DataFrame()

        indexDf = self.getDataLocal(CodeList=indexCodeList,dataFlag='Index',method=method)
        if not indexDf.empty:
            return indexDf

        if SourceFlag == 'Wind':
            w.start()
            filed = 'close'

            tempIndexValue = w.wsd(codes=indexCodeList, fields=filed, beginTime=startDate, endTime=endDate,
                                 options='')
            if tempIndexValue.ErrorCode != 0:
                self.PrintInfoDemo.PrintLog(infostr='wind读取指数数据失败，错误代码： ', otherInfo=tempIndexValue.ErrorCode)
                return pd.DataFrame()

            IndexValueDf = pd.DataFrame(tempIndexValue.Data, index=tempIndexValue.Codes, columns=tempIndexValue.Times).T
            writer = pd.ExcelWriter(
                r"C:\\Users\\lenovo\\PycharmProjects\\FundPoolSelect\\GetDataSource\\HistoryData\\" + "IndexValueDf.xlsx")
            IndexValueDf.to_excel(writer)
            writer.save()
            self.PrintInfoDemo.PrintLog(infostr='wind读取指数数据成功，存入本地文件 ')
            w.close()
            return IndexValueDf
        else:
            thsLogin = THS_iFinDLogin("zszq5072", "754628")
            if thsLogin not in [0, -201]:
                self.PrintInfoDemo.PrintLog('登录ifind失败，请检查！')
                return pd.DataFrame()

            codeListStr = ','.join(indexCodeList)
            indicators = 'ths_close_price_index'
            initParams=''
            params = 'Days:Tradedays,Fill:Previous,Interval:D'
            data = THS_DateSerial(codeListStr, indicators,initParams,params, startDate, endDate)

            if data['errorcode'] != 0:
                self.PrintInfoDemo.PrintLog(infostr='ifind获取指数数据失败，错误代码： ', otherInfo=data['errorcode'])
                return pd.DataFrame()
            tData = THS_Trans2DataFrame(data)
            dfListIn = []
            for code, tempdf in tData.groupby(by=['thscode']):
                tempdf.set_index('time', drop=True, inplace=True)
                tempFianlDf = tempdf.rename(columns={indicators: code}).drop(labels=['thscode'], axis=1)
                dfListIn.append(tempFianlDf)
            IndexValueDf = pd.concat(dfListIn, axis=1, join='outer')
            writer = pd.ExcelWriter( r"C:\\Users\\lenovo\\PycharmProjects\\FundPoolSelect\\GetDataSource\\HistoryData\\" + "IndexValueDf.xlsx" )
            IndexValueDf.to_excel(writer)
            writer.save()
            self.PrintInfoDemo.PrintLog(infostr='ifind读取指数数据成功，存入本地文件 ')
            thsLogout = THS_iFinDLogout()
            return IndexValueDf

    def getMain(self,method='NotBench'):
        fundPoolDf = self.getDataLocal(dataFlag='InitFund')
        netValueDf = self.getFundNetData(fundCodeList=fundPoolDf[u'证券代码'].tolist())
        if netValueDf.empty:
            netValueDf = self.getFundNetData(fundCodeList=fundPoolDf[u'证券代码'].tolist(),SourceFlag='Ifind')
        self.PrintInfoDemo.PrintLog('获取基金历史净值数据完成！ ')

        indexPoolDf = self.getDataLocal(dataFlag='InitIndex')
        indexValueDf = self.getIndexData(indexCodeList=indexPoolDf[u'证券代码'].tolist(),method=method)
        if indexValueDf.empty:
            indexValueDf = self.getIndexData(indexCodeList=indexPoolDf[u'证券代码'].tolist(), SourceFlag='Ifind')
        self.PrintInfoDemo.PrintLog('获取指数历史数据完成！ ')

        dicResult = {}
        dicResult['fundPoolDf']=fundPoolDf
        dicResult['netValueDf'] = netValueDf
        dicResult['indexPoolDf'] = indexPoolDf
        dicResult['indexValueDf'] = indexValueDf
        return dicResult

if __name__ == '__main__':
    GetProductDataDemo = GetFundPool()
    GetProductDataDemo.getMain()
