# -- coding: utf-8 --

'''
    基于基金的归因分析模型（CL）的筛选：
    数据源：
        （1）基金池：除指数基金外的其他国内权益类基金
        （2）基准指数池：中证基金系列指数、沪深市场基准指数
        （3）以上均来自wind/ifind
    逻辑：
        （1）获取基金池和基准指数池数据，清洗
        （2）对基金池的每只基金，基准指数池的每只指数，循环线性回归，回归模型为CL模型
        （3）记录每次回归时的结果：R^2，截距项alpha(选股能力),回归系数差值betaDiff（择时能力）
        （4）对每只产品回归记录的结果，按照R^2最大，即对其解释程度最强的指数，找到对应的指数
        （5）按照（4）中找到的基准指数，定位对应的alpha,betaDiff值
        （6）分别按照（5）中各基金的alpha,betaDiff值排序。
        （7）对alpha,betaDiff排序后的值相加（相当于alpha ,betaDiff等权重），得到最终排名
'''

import pandas as pd
import numpy as np
from datetime import datetime, date
from GetDataSource.GetFundPool import GetFundPool
from PrintInfo import PrintInfo
import matplotlib.pyplot as plt
from sklearn.linear_model import LinearRegression
from FundAnyMain.CalcRiskReturnToExcel import CalcRiskReturnToExcel
import warnings

warnings.filterwarnings("ignore")

import matplotlib

matplotlib.rcParams['font.sans-serif'] = ['SimHei']
matplotlib.rcParams['font.family'] = 'sans-serif'
matplotlib.rcParams['axes.unicode_minus'] = False


class FundAnalyze:

    def __init__(self):
        self.PrintInfoDemo = PrintInfo()
        self.riskFree = 0  # 无风险利率
        calcDate = {}
        calcDate['oneMonth'] = (u'近一月', 21 * 1)
        calcDate['ThreeMonths'] = (u'近三月', 21 * 3)
        calcDate['SixMonths'] = (u'近六月', 21 * 6)
        calcDate['OneYear'] = (u'近一年', 21 * 12)
        calcDate['TwoYears'] = (u'近两年', 21 * 12 * 2)
        calcDate['ThreeYears'] = (u'近三年', 21 * 12 * 3)
        calcDate['TotalPeriod'] = (u'成立以来', np.inf)
        self.calcDate = calcDate

    def getRollingClModel(self, fundIndexReturnDf, fundCode, indexCode):
        rollNum = 250
        if fundIndexReturnDf.shape[0] > rollNum:
            RSquareList = []
            alphaValueList = []
            betaDiffList = []
            interDf = int((fundIndexReturnDf.shape[0] - rollNum) / 10)
            for knum in range(rollNum, fundIndexReturnDf.shape[0], interDf):
                tempDf = fundIndexReturnDf.iloc[knum:knum + rollNum]

                tempDf['Y'] = tempDf[fundCode] - self.riskFree
                tempDf['X1'] = tempDf[indexCode] - self.riskFree
                tempDf.loc[tempDf['X1'] < 0, 'X1'] = 0
                tempDf['X2'] = tempDf[indexCode] - self.riskFree
                tempDf.loc[tempDf['X2'] > 0, 'X2'] = 0
                X = tempDf[['X1', 'X2']].values.reshape((-1, 2))
                y = tempDf['Y'].values.reshape(-1)
                reg = LinearRegression().fit(X, y)

                RSquareList.append(reg.score(X, y))
                alphaValueList.append(reg.intercept_)
                betaDiffList.append(reg.coef_[0] - reg.coef_[1])
            RSquare = np.mean(RSquareList)
            alphaValue = np.mean(alphaValueList)
            betaDiff = np.mean(betaDiffList)
        else:
            tempDf = fundIndexReturnDf

            tempDf['Y'] = tempDf[fundCode] - self.riskFree
            tempDf['X1'] = tempDf[indexCode] - self.riskFree
            tempDf.loc[tempDf['X1'] < 0, 'X1'] = 0
            tempDf['X2'] = tempDf[indexCode] - self.riskFree
            tempDf.loc[tempDf['X2'] > 0, 'X2'] = 0
            X = tempDf[['X1', 'X2']].values.reshape((-1, 2))
            y = tempDf['Y'].values.reshape(-1)
            reg = LinearRegression().fit(X, y)
            RSquare = reg.score(X, y)
            alphaValue = reg.intercept_
            betaDiff = reg.coef_[0] - reg.coef_[1]

        LinearResult = {}
        LinearResult['RSquare'] = RSquare
        LinearResult['alphaValue'] = alphaValue
        LinearResult['betaDiff'] = betaDiff
        return LinearResult



    def getCLModel(self, fundIndexReturnDf, fundCode, indexCode):
        '''
        C-L模型回归，得到基金的选股能力，择时能力
        :param fundIndexReturnDf:
        :param fundCode:
        :param indexCode:
        :return:
        '''

        tempDf = fundIndexReturnDf.copy()
        tempDf['Y'] = tempDf[fundCode] - self.riskFree
        tempDf['X1'] = tempDf[indexCode] - self.riskFree
        tempDf.loc[tempDf['X1'] < 0, 'X1'] = 0
        tempDf['X2'] = tempDf[indexCode] - self.riskFree
        tempDf.loc[tempDf['X2'] > 0, 'X2'] = 0
        X = tempDf[['X1', 'X2']].values.reshape((-1, 2))
        y = tempDf['Y'].values.reshape(-1)
        reg = LinearRegression().fit(X, y)
        RSquare = reg.score(X, y)
        alphaValue = reg.intercept_
        betaDiff = reg.coef_[0] - reg.coef_[1]

        LinearResult = {}
        LinearResult['RSquare'] = RSquare
        LinearResult['alphaValue'] = alphaValue
        LinearResult['betaDiff'] = betaDiff
        return LinearResult

    def saveDfToExcel(self, tempDf, excelPath):
        writer = pd.ExcelWriter(excelPath)
        tempDf.to_excel(writer)
        writer.save()

    def getCorrMax(self, netValueDf, indexValueDf):
        '''
        获取每个基金与之相关性最强的指数
        :param netValueDf: 基金历史净值数据
        :param indexValueDf: 指数历史数据
        :return:
        '''

        dicCorr = {}
        for fundCode in netValueDf:
            corrValue = 0
            dicCorr[fundCode] = {}
            for indexCode in indexValueDf:
                tempIndexFund = pd.concat([netValueDf[fundCode], indexValueDf[indexCode]], axis=1, join='inner')
                tempIndexFund = tempIndexFund.dropna()
                corr = tempIndexFund.corr().ix[0, 1]
                if corr > corrValue:
                    corrValue = corr
                    corrIndexCode = indexCode
            dicCorr[fundCode]['corrValue'] = corrValue
            dicCorr[fundCode]['indexCode'] = corrIndexCode
        corrIndexDf = pd.DataFrame(dicCorr)
        excelPath = r"C:\\Users\\lenovo\\PycharmProjects\\FundPoolSelect\\GetDataSource\\AnalyzeDAta\\"
        self.saveDfToExcel(corrIndexDf, excelPath + "corrIndexDf.xlsx")
        self.PrintInfoDemo.PrintLog('相关基准指数计算完成！')

    def getPeriodAnalyze(self, netValueDf, indexValueDf, Period='ThreeMonths'):
        calcResult = {}

        calcDateSort = sorted(self.calcDate.items(), key=lambda x: x[1][1], reverse=False)
        calcFinal = False
        for periodData in calcDateSort:
            self.PrintInfoDemo.PrintLog('当前回归周期为：%s' % periodData[1][0])

            if calcFinal:
                break

            valueNum = periodData[1][1]
            if netValueDf.shape[0] < valueNum:
                periodNetValueDf = netValueDf
                calcFinal = True
            else:
                if np.isinf(valueNum):
                    periodNetValueDf = netValueDf
                else:
                    periodNetValueDf = netValueDf.iloc[-valueNum:]
            calcResult[periodData[1][0]] = self.getAnalyzeToExcel(periodNetValueDf, indexValueDf,
                                                                  period=periodData[1][0])

        return calcResult

    def getAnalyzeToExcel(self, netValueDf, indexValueDf, period='成立以来'):
        '''
        对所有基金，所有指数循环回归，并将结果存入本地
        :return:
        '''

        # self.getCorrMax(netValueDf,indexValueDf)

        dicCLRSquare = {}
        dicCLAlpha = {}
        dicClBetaDiff = {}

        calcTime = 0
        for fundCode in netValueDf:
            calcTime = calcTime + 1
            self.PrintInfoDemo.PrintLog('总回归基金数量：%s,当前基金：%s，剩余回归基金数量：%s' %
                                        (str(netValueDf.shape[1]), fundCode, str(netValueDf.shape[1] - calcTime)))
            dicCLRSquare[fundCode] = {}
            dicCLAlpha[fundCode] = {}
            dicClBetaDiff[fundCode] = {}
            for indexCode in indexValueDf:
                fundIndexDf = pd.concat([netValueDf[fundCode], indexValueDf[indexCode]], axis=1, join='inner')
                fundIndexDf = fundIndexDf.dropna()
                fundIndexReturnDf = (fundIndexDf - fundIndexDf.shift(1)) / fundIndexDf.shift(1)
                fundIndexReturnDf = fundIndexReturnDf.fillna(0)
                dicClResult = self.getCLModel(fundIndexReturnDf, fundCode, indexCode)
                dicCLRSquare[fundCode][indexCode] = dicClResult['RSquare']
                dicCLAlpha[fundCode][indexCode] = dicClResult['alphaValue']
                dicClBetaDiff[fundCode][indexCode] = dicClResult['betaDiff']

        RSquareDf = pd.DataFrame(dicCLRSquare)
        alphaValueDf = pd.DataFrame(dicCLAlpha)
        betaDiffDf = pd.DataFrame(dicClBetaDiff)

        excelPath = r"C:\\Users\\lenovo\\PycharmProjects\\FundPoolSelect\\GetDataSource\\AnalyzeDAta\\"
        self.saveDfToExcel(RSquareDf, excelPath + "%sRSquareDf.xlsx" % period)
        self.saveDfToExcel(alphaValueDf, excelPath + "%salphaValueDf.xlsx" % period)
        self.saveDfToExcel(betaDiffDf, excelPath + "%sbetaDiffDf.xlsx" % period)

        dicAny = {}
        dicAny['RSquareDf'] = RSquareDf
        dicAny['alphaValueDf'] = alphaValueDf
        dicAny['betaDiffDf'] = betaDiffDf
        dicAny['netValueDf'] = netValueDf
        dicAny['indexValueDf'] = indexValueDf
        return dicAny

    def getAnyResult(self):
        '''
        从本地获取分析结果
        :return:
        '''
        dicRegre = {}
        localPath = r"C:\\Users\\lenovo\\PycharmProjects\\FundPoolSelect\\GetDataSource\\AnalyzeDAta\\NotBench\\"
        try:
            for key, periodStr in self.calcDate.items():
                dicRegre[periodStr[0]] = {}

                alphaPath = localPath + "%salphaValueDf.xlsx" % periodStr[0]
                dicRegre[periodStr[0]]['alphaValueDf'] = pd.read_excel(alphaPath)

                betaPath = localPath + "%sbetaDiffDf.xlsx" % periodStr[0]
                dicRegre[periodStr[0]]['betaDiffDf'] = pd.read_excel(betaPath)

                RSquareDfPath = localPath + "%sRSquareDf.xlsx" % periodStr[0]
                dicRegre[periodStr[0]]['RSquareDf'] = pd.read_excel(RSquareDfPath)

            netValueDfPath = localPath + "netValueDf.xlsx"
            netValueDf = pd.read_excel(netValueDfPath)

            indexValueDfPath = localPath + "indexValueDf.xlsx"
            indexValueDf = pd.read_excel(indexValueDfPath)

            dicRegre['netValueDf'] = netValueDf
            dicRegre['indexValueDf'] = indexValueDf

        except:
            self.PrintInfoDemo.PrintLog('未读取到本地回归分析结果数据，请检查！')
        return dicRegre

    def deepAnalyze(self, dicAny):
        dicAlphaAndBetaDf = {}
        for key, periodStr in self.calcDate.items():

            alphaValueDf = dicAny[periodStr[0]]['alphaValueDf']
            betaDiffDf = dicAny[periodStr[0]]['betaDiffDf']
            RSquareDf = dicAny[periodStr[0]]['RSquareDf']

            RSquareMaxLoc = RSquareDf.idxmax()
            RSquareMaxLoc.name = 'RSquareMaxLoc'

            RSquareMaxValue = RSquareDf.max()
            RSquareMaxValue.name = 'RSquareMaxValue'
            RSquareMaxDf = pd.concat([RSquareMaxValue, RSquareMaxLoc], axis=1)

            alphaDic = {}
            betaDiffDic = {}
            for fundCode in RSquareMaxDf.index.tolist():
                alphaDic[fundCode] = {}
                betaDiffDic[fundCode] = {}
                alphaDic[fundCode]['alphaValue'] = alphaValueDf.ix[
                    RSquareMaxDf.loc[fundCode, 'RSquareMaxLoc'], fundCode]
                betaDiffDic[fundCode]['betaDiffValue'] = betaDiffDf.ix[
                    RSquareMaxDf.loc[fundCode, 'RSquareMaxLoc'], fundCode]
            alphaAndBetaDf = pd.concat([pd.DataFrame(alphaDic), pd.DataFrame(betaDiffDic)], axis=0).T
            alphaAndBetaDf['alphaValueRank'] = alphaAndBetaDf['alphaValue'].rank(ascending=False)
            alphaAndBetaDf['betaDiffValueRank'] = alphaAndBetaDf['betaDiffValue'].rank(ascending=False)
            alphaAndBetaDf['totalRank'] = alphaAndBetaDf[['alphaValueRank', 'betaDiffValueRank']].sum(axis=1)
            alphaAndBetaDf.sort_values('totalRank', inplace=True)
            dicAlphaAndBetaDf[periodStr[0]] = alphaAndBetaDf['totalRank']
        rankDf = pd.DataFrame(dicAlphaAndBetaDf)
        rankDf['finalRank'] = rankDf.sum(axis=1)
        rankDf.sort_values('finalRank', inplace=True)
        localPath = r"C:\\Users\\lenovo\\PycharmProjects\\FundPoolSelect\\GetDataSource\\AnalyzeDAta\\NotBench\\"
        self.saveDfToExcel(rankDf, localPath + "rankDf.xlsx")
        return rankDf

    def getStatistical(self, dicAny, regressDf):
        '''
        计算基金池风险收益指标，并观察期排序后各风险收益指标图的规律
        :param dicAny:
        :param regressDf:
        :return:
        '''
        demoRegre = regressDf
        fundCodeList = demoRegre.index.tolist()
        netValueDf = dicAny['netValueDf']
        indexValueDf = dicAny['indexValueDf']
        RSquareDf = dicAny[u'成立以来']['RSquareDf']

        CalcRiskReturnToExcelDemo = CalcRiskReturnToExcel()
        dicResult = {}
        for key, periodStr in CalcRiskReturnToExcelDemo.calcDate.items():
            dicResult[periodStr[0]] = {}
            dicResult[periodStr[0]]['annualReturn'] = []
            dicResult[periodStr[0]]['annualStd'] = []
            dicResult[periodStr[0]]['maxDown'] = []
            dicResult[periodStr[0]]['sharpRate'] = []
            dicResult[periodStr[0]]['calmaRate'] = []

        for fundCode in fundCodeList:
            demoNetDf = netValueDf[fundCode]
            indexCode = RSquareDf[RSquareDf[fundCode] == RSquareDf[fundCode].max()].index.tolist()[0]
            tempDf = pd.concat([demoNetDf, indexValueDf[indexCode]], axis=1, join='inner')
            tempDf = tempDf.dropna()
            tempReturn = (tempDf - tempDf.shift(1)) / tempDf.shift(1)
            tempReturn.fillna(0, inplace=True)

            dateList = [datetime.strptime(dateStr, "%Y-%m-%d") for dateStr in tempReturn.index.tolist()]
            tempReturn = pd.DataFrame(tempReturn.values, index=dateList, columns=tempReturn.columns)
            resultIndicator = CalcRiskReturnToExcelDemo.GoMain(tempReturn)

            for key, periodStr in CalcRiskReturnToExcelDemo.calcDate.items():
                dicResult[periodStr[0]]['annualReturn'].append(
                    resultIndicator.loc[periodStr[0], fundCode]['年化收益']-resultIndicator.loc[periodStr[0], indexCode]['年化收益'])
                dicResult[periodStr[0]]['annualStd'].append(resultIndicator.loc[periodStr[0], fundCode]['年化波动'])
                dicResult[periodStr[0]]['maxDown'].append(resultIndicator.loc[periodStr[0], fundCode]['最大回撤'])
                dicResult[periodStr[0]]['sharpRate'].append(resultIndicator.loc[periodStr[0], fundCode]['夏普比率'])
                dicResult[periodStr[0]]['calmaRate'].append(resultIndicator.loc[periodStr[0], fundCode]['卡玛比率'])

        annualReturnList = []
        sharpRateList = []
        annualStdList = []
        maxDownList = []
        for stPeriod, indicator in dicResult.items():
            annualReturnList.append(pd.DataFrame(indicator['annualReturn'], index=fundCodeList, columns=[stPeriod]))
            sharpRateList.append(pd.DataFrame(indicator['sharpRate'], index=fundCodeList, columns=[stPeriod]))
            annualStdList.append(pd.DataFrame(indicator['annualStd'], index=fundCodeList, columns=[stPeriod]))
            maxDownList.append(pd.DataFrame(indicator['annualStd'], index=fundCodeList, columns=[stPeriod]))

        annualReturnDf = pd.concat(annualReturnList, axis=1)
        sharpRateDf = pd.concat(sharpRateList, axis=1)
        annualStdDf = pd.concat(annualStdList, axis=1)
        maxDownDf = pd.concat(maxDownList, axis=1)

        fig = plt.figure(figsize=(16, 9))

        tempDf = annualReturnDf.copy()
        tempDf = tempDf.drop('近一月', axis=1)
        axNum = 0
        rowNum = int(np.ceil(tempDf.shape[1] / 2))
        colNum = 2
        for dateLabel in tempDf.columns.tolist():
            axNum = axNum + 1
            ax = fig.add_subplot(int(str(rowNum) + str(colNum) + str(axNum)))
            tempDf['Y'] = tempDf[dateLabel]
            tempDf['X'] = list(range(annualReturnDf.shape[0]))

            X = tempDf[['X']].values.reshape((-1, 1))
            y = tempDf['Y'].values.reshape(-1)
            reg = LinearRegression().fit(X, y)
            tempDf['LineRegress'] = reg.predict(X)
            tempDf.plot(ax=ax, kind='scatter', x='X', y=dateLabel)
            tempDf['LineRegress'].plot(ax=ax, color='r')
        plt.tight_layout()
        localPath = r"C:\\Users\\lenovo\\PycharmProjects\\FundPoolSelect\\GetDataSource\\AnalyzeDAta\\NotBench\\"
        plt.savefig(localPath + '样本基金收益统计图.png')

        # ax1=fig.add_subplot(221)
        # annualReturnDf['近六月'].plot(ax=ax1)
        # ax1.set_title('年化收益')
        #
        # ax2 = fig.add_subplot(222)
        # annualStdDf.plot(ax=ax2)
        # ax2.set_title('年化波动')
        #
        # ax3 = fig.add_subplot(223)
        # sharpRateDf.plot(ax=ax3)
        # ax3.set_title('夏普比率')
        #
        # ax4 = fig.add_subplot(224)
        # maxDownDf.plot(ax=ax4)
        # ax4.set_title('最大回撤')

        plt.show()

    def plotDemo(self, dicAny, regressDf,PlotFig='before'):
        if PlotFig=='before':
            demoRegre = regressDf.iloc[:6]
            nameStr = '前六'
        else:
            nameStr='后六'
            demoRegre = regressDf.iloc[-6:]
        fundCodeList = demoRegre.index.tolist()
        netValueDf = dicAny['netValueDf']
        indexValueDf = dicAny['indexValueDf']
        RSquareDf = dicAny[u'成立以来']['RSquareDf']

        CalcRiskReturnToExcelDemo = CalcRiskReturnToExcel()
        localPath = r"C:\\Users\\lenovo\\PycharmProjects\\FundPoolSelect\\GetDataSource\\AnalyzeDAta\\NotBench\\"

        fig = plt.figure(figsize=(16, 9))
        plotNum = 0
        for fundCode in fundCodeList:
            plotNum = plotNum + 1
            demoNetDf = netValueDf[fundCode]
            index1List = RSquareDf[RSquareDf[fundCode] == RSquareDf[fundCode].max()].index.tolist()
            tempDf = pd.concat([demoNetDf, indexValueDf[index1List[0]]], axis=1, join='inner')
            tempDf = tempDf.dropna()
            tempReturn = (tempDf - tempDf.shift(1)) / tempDf.shift(1)
            tempReturn.fillna(0, inplace=True)

            dateList = [datetime.strptime(dateStr, "%Y-%m-%d") for dateStr in tempReturn.index.tolist()]
            tempReturn = pd.DataFrame(tempReturn.values, index=dateList, columns=tempReturn.columns)

            CalcRiskReturnToExcelDemo.GoMain(tempReturn, toExcelPath=localPath + '%s.xls' % fundCode)

            axNum = fig.add_subplot(int('32' + str(plotNum)))
            (1 + tempReturn).cumprod().plot(ax=axNum)
            axNum.grid()
        plt.tight_layout()
        plt.savefig(localPath+'%s走势图.png'%nameStr)
        plt.show()

        dfList = []
        for code in fundCodeList:
            riskDf = pd.read_excel(localPath + '%s.xls' % code,)
            riskDf['统计周期'].fillna(method='pad',inplace=True)
            riskDf=riskDf.set_index([u'统计周期',u'指标'])
            dfList.append(riskDf)
        totalDf =pd.concat(dfList,axis=1)
        self.saveDfToExcel(totalDf, localPath + "totalDf_%s.xlsx"%PlotFig)

    def getMain(self):
        dicAny = self.getAnyResult()
        if not dicAny:
            self.PrintInfoDemo.PrintLog('获取基金净值和指数数据...')
            GetFundPoolDemo = GetFundPool()
            self.dicResult = GetFundPoolDemo.getMain()
            if self.dicResult['netValueDf'].empty or self.dicResult['indexValueDf'].empty:
                self.PrintInfoDemo.PrintLog('历史数据获取失败，请检查！')
                return
            localPath = r"C:\\Users\\lenovo\\PycharmProjects\\FundPoolSelect\\GetDataSource\\AnalyzeDAta\\"
            self.saveDfToExcel(self.dicResult['netValueDf'], localPath + "netValueDf.xlsx")
            self.saveDfToExcel(self.dicResult['indexValueDf'], localPath + "indexValueDf.xlsx")
            self.PrintInfoDemo.PrintLog('获取基金净值和指数数据成功！')
            # dicAny = self.getAnalyzeToExcel(self.dicResult['netValueDf'], self.dicResult['indexValueDf'],period='成立以来')
            dicAny = self.getPeriodAnalyze(self.dicResult['netValueDf'], self.dicResult['indexValueDf'])

        regressDf = self.deepAnalyze(dicAny)
        self.getStatistical(dicAny=dicAny, regressDf=regressDf)
        # self.plotDemo(dicAny=dicAny, regressDf=regressDf,PlotFig='before')


if __name__ == '__main__':
    FundAnalyzeDemo = FundAnalyze()
    FundAnalyzeDemo.getMain()
