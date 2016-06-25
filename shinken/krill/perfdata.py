import re
import operator
from shinken.misc.perfdata import Metric, PerfDatas
from shinken.log import logger

OK = 0
WARNING = 1
CRITICAL = 2
UNKNOWN = 3


def check_value(metric, name, warning, critical):
    if float(warning) < float(critical):
        op_func, op_text = operator.gt, '>'
    else:
        op_func, op_text = operator.lt, '<'

    if op_func(float(metric.value), float(critical)):
        return (CRITICAL, '%s=%s%s %s %s%s!!' % (name, metric.value, metric.uom, op_text, critical, metric.uom))
    if op_func(float(metric.value), float(warning)):
        return (WARNING, '%s=%s%s %s %s%s!' % (name, metric.value, metric.uom, op_text, warning, metric.uom))
    return (OK, '%s=%s%s' % (name, metric.value, metric.uom))


def process_perfdata(obj, s, prefix=''):
    p = PerfDatas(s)
    if prefix:
        prefix += '_'

    checks=[]
    for metric in p:
        # print 'm,M', metric.value, metric.min, metric.max

        if float(metric.value) < float(metric.min):
            return 'UNKNOWN', '%s=%s%s below min(%s%s)' % (metric.name, metric.value, metric.uom, metric.min, metric.uom)
        if float(metric.value) > float(metric.max):
            return 'UNKNOWN', '%s=%s%s above max(%s%s)' % (metric.name, metric.value, metric.uom, metric.max, metric.uom)

        thresholds_name = '%s%s_thresholds' % (prefix, metric.name)
        if hasattr(obj, thresholds_name):
            warning, critical = getattr(obj, thresholds_name).split(',')
            # print 'w,c', warning, critical
            checks.append(check_value(metric, metric.name, warning, critical))
    if CRITICAL in [chk[0] for chk in checks]:
        return 'CRITICAL', 'CRITICAL - ' + ' '.join([chk[1] for chk in checks if chk[0] == CRITICAL])
    if WARNING in [chk[0] for chk in checks]:
        return 'WARNING', 'WARNING - ' + ' '.join([chk[1] for chk in checks if chk[0] == WARNING])
    return 'OK', 'OK - ' + ' '.join([chk[1] for chk in checks])


class PerfDef(object):

    def __init__(self, perf_def):
        if len(perf_def) == 3: #patter/format/unit
            self.pattern, self.format, self.unit = perf_def
            thresholds = []
            self.min = self.max = None
        else:
            self.pattern, self.format, self.unit, thresholds, self.min, self.max = perf_def[0:6]

        self.exceptions = []
        if len(perf_def) == 7:
            self.exceptions = perf_def[6]

        if len(thresholds) == 0:
            self.low_critical = self.low_warning = self.warning = self.critical = None
        if len(thresholds) == 2:
            self.warning, self.critical = thresholds
            self.low_critical = self.low_warning = None
        if len(thresholds) == 4:
            self.low_critical, self.low_warning, self.warning, self.critical = thresholds


    def __str__(self):
        return "p%s/f%s/u%s/m%s/M%s lw%s/lc%s/w%s/c%s" % (self.pattern, self.format, self.unit, self.min, self.max, self.low_critical, self.low_warning, self.warning, self.critical)


    @property
    def is_checked(self):
        return self.warning is not None


    def filter_metric(self, metric):
        if re.match(r'^%s(\d*)$' % self.pattern, metric):
            return True
        else:
            return False


    def get_perf(self, metric, value):
        if self.is_checked:
            try:
                return '{metric}={value:{format}}{unit};{warning:{format}};{critical:{format}};{min:{format}};{max:{format}}'.format(
                    metric=metric,
                    value=value,
                    warning=self.warning,
                    critical=self.critical,
                    min=self.min,
                    max=self.max,
                    format=self.format,
                    unit=self.unit,
                )
            except Exception, exc:
                print 'get_perf Exception', exc, metric, value, type(value), self.warning, self.critical, self.min, type(self.min), self.max, type(self.max), self.format, self.unit
        else:
            return '{metric}={value:{format}}{unit}'.format(
                metric=metric,
                value=value,
                format=self.format,
                unit=self.unit,
            )


    def get_checks(self, metric, value):
        checks = []
        if float(value) < float(self.min) and value not in self.exceptions:
            checks.append((UNKNOWN, '{metric}={value:{format}}{unit} below min({min}{unit})'.format(
                metric=metric,
                value=value,
                min=self.min,
                format=self.format,
                unit=self.unit,
            )))
        elif float(value) > float(self.max) and value not in self.exceptions:
            checks.append((UNKNOWN, '{metric}={value:{format}}{unit} above max({max}{unit})'.format(
                metric=metric,
                value=value,
                max=self.max,
                format=self.format,
                unit=self.unit,
            )))
        else:
            checks.append(self._check_value(metric, value, self.warning, self.critical))
            if self.low_critical and self.low_warning:
                checks.append(self._check_value(metric, value, self.low_warning, self.low_critical))
        return list(set(checks))


    def _check_value(self, metric, value, warning, critical):
        # print '_check_value', warning, critical
        if float(warning) < float(critical):
            op_func, op_text = operator.gt, '>'
        else:
            op_func, op_text = operator.lt, '<'

        if critical is not None and op_func(float(value), float(critical)) and value not in self.exceptions:
            return (CRITICAL, '{metric}={value:{format}}{unit} {op_text} {critical:{format}}{unit}!!'.format(
                        metric=metric,
                        value=value,
                        format=self.format,
                        unit=self.unit,
                        op_text=op_text,
                        critical=critical
                    ))
        if warning is not None and op_func(float(value), float(warning)) and value not in self.exceptions:
            return (WARNING, '{metric}={value:{format}}{unit} {op_text} {warning:{format}}{unit}!'.format(
                        metric=metric,
                        value=value,
                        format=self.format,
                        unit=self.unit,
                        op_text=op_text,
                        warning=warning
                    ))
        return (OK, '{metric}={value:{format}}{unit}'.format(
                        metric=metric,
                        value=value,
                        format=self.format,
                        unit=self.unit,
                    ))



def process_raw_perfdata(raw_data, perf_defs):

    # def _check_value(warning, critical):
    #     if float(warning) < float(critical):
    #         op_func, op_text = operator.gt, '>'
    #     else:
    #         op_func, op_text = operator.lt, '<'

    #     if critical and op_func(float(value), float(critical)):
    #         return (CRITICAL, '{metric}={value:{format}}{unit} {op_text} {critical:{format}}{unit}!!'.format(
    #                     metric=metric,
    #                     value=value,
    #                     format=format,
    #                     unit=unit,
    #                     op_text=op_text,
    #                     critical=critical
    #                 ))
    #     if warning and op_func(float(value), float(warning)):
    #         return (WARNING, '{metric}={value:{format}}{unit} {op_text} {warning:{format}}{unit}!'.format(
    #                     metric=metric,
    #                     value=value,
    #                     format=format,
    #                     unit=unit,
    #                     op_text=op_text,
    #                     warning=warning
    #                 ))
    #     return (OK, '{metric}={value:{format}}{unit}'.format(
    #                     metric=metric,
    #                     value=value,
    #                     format=format,
    #                     unit=unit,
    #                 ))

    checks = []
    perfs = []
    for perf_def in perf_defs:
        pd = PerfDef(perf_def)
        # print pd
        # pattern, format, unit, thresholds, min, max = perf_def

        # if len(thresholds) == 2:
        #     warning, critical = thresholds
        #     low_critical = low_warning = None
        # if len(thresholds) == 4:
        #     low_critical, low_warning, warning, critical = thresholds

        for metric, value in raw_data.iteritems():
            if value is None:
                continue

            if pd.filter_metric(metric):
                perf = pd.get_perf(metric, value)
                perfs.append(perf)

                if pd.is_checked:
                    checks.extend(pd.get_checks(metric, value))

                # print '--', checks

            # continue

            # if re.match(r'%s(\d*)' % pattern, metric):
            #     try:
            #         # print 'process_raw_perfdata', metric, value, warning, critical, min, max, format, unit
            #         perfs.append('{metric}={value:{format}}{unit};{warning:{format}};{critical:{format}};{min:{format}};{max:{format}}'.format(
            #                 metric=metric,
            #                 value=value,
            #                 warning=warning,
            #                 critical=critical,
            #                 min=min,
            #                 max=max,
            #                 format=format,
            #                 unit=unit,
            #             ))
            #     except Exception, exc:
            #         print 'process_raw_perfdata Exception', exc, metric, value, type(value), warning, critical, min, type(min), max, type(max), format, unit

            #     if min is not None and float(value) < float(min):
            #         checks.append((UNKNOWN, '{metric}={value:{format}}{unit} below min({min}{unit})'.format(
            #             metric=metric,
            #             value=value,
            #             min=min,
            #             format=format,
            #             unit=unit,
            #         )))
            #     elif max is not None and float(value) > float(max):
            #         checks.append((UNKNOWN, '{metric}={value:{format}}{unit} above max({max}{unit})'.format(
            #             metric=metric,
            #             value=value,
            #             max=max,
            #             format=format,
            #             unit=unit,
            #         )))
            #     elif warning is not None and critical is not None:
            #         checks.append(_check_value(warning, critical))
            #         if low_critical and low_warning:
            #             checks.append(_check_value(low_warning, low_critical))

    if UNKNOWN in [chk[0] for chk in checks]:
        return 'UNKNOWN', 'UNKNOWN - ' + ' '.join([chk[1] for chk in checks if chk[0] == UNKNOWN]), ' '.join(perfs)
    if CRITICAL in [chk[0] for chk in checks]:
        return 'CRITICAL', 'CRITICAL - ' + ' '.join([chk[1] for chk in checks if chk[0] == CRITICAL]), ' '.join(perfs)
    if WARNING in [chk[0] for chk in checks]:
        return 'WARNING', 'WARNING - ' + ' '.join([chk[1] for chk in checks if chk[0] == WARNING]), ' '.join(perfs)
    return 'OK', 'OK - ' + ' '.join([chk[1] for chk in checks]), ' '.join(perfs)



def test_process_raw_perfdata():
    # from collections import namedtuple
    # SnmpPerf = namedtuple('SnmpPerf', ['dnsnr', 'dnsnr21', 'dnsnr21', 'dnsnr', 'dnsnr21', 'dnsnr21'])

    raw_data = {
        'dnsnr': 51.2,
        'dnsnr21': 52,
        'dnsnr22': 50,

        'uptx': 23,
        'uptx12': 23.12,
        'uptx23': 23.34,

        'dnrx': -14,
        'freq7': 115000000,

        'too12': 690,
        'upsnr1': 20,
        'upsnr10': 0.0,
    }
    tflk = {
        'dnatt': 47.362500000000004,
        'dnatt1': 44.5,
        # 'dnatt2': 45.5,
        # 'dnatt3': 46.3,
        # 'dnatt4': 47.3,
        # 'dnatt5': 48.0,
        # 'dnatt6': 48.5,
        # 'dnatt7': 48.9,
        # 'dnatt8': 49.9,
        # 'dnbw': 3388.925303048435,
        # 'dncorr': 0.00019051989916840176,
        # 'dncorr1': 1.8812183673131536e-05,
        # 'dncorr2': 0.0003009969206133791,
        # 'dncorr3': 0.0001316973016539864,
        # 'dncorr4': 1.8814332080863245e-05,
        # 'dncorr5': 0.00024465867761984747,
        # 'dncorr6': 7.528066986245656e-05,
        # 'dncorr7': 0.00026347594784531254,
        # 'dncorr8': 0.00047054368311103906,
        # 'dnfreq1': 115000000,
        # 'dnfreq2': 123000000,
        # 'dnfreq3': 131000000,
        # 'dnfreq4': 139000000,
        # 'dnfreq5': 147000000,
        # 'dnfreq6': 155000000,
        # 'dnfreq7': 163000000,
        # 'dnfreq8': 171000000,
        # 'dnko': 0.0,
        # 'dnko1': 0.0,
        # 'dnko2': 0.0,
        # 'dnko3': 0.0,
        # 'dnko4': 0.0,
        # 'dnko5': 0.0,
        # 'dnko6': 0.0,
        # 'dnko7': 0.0,
        # 'dnko8': 0.0,
        # 'dnok': 100,
        # 'dnrx': 0.6375000000000001,
        # 'dnrx1': 3.5,
        # 'dnrx2': 2.5,
        # 'dnrx3': 1.7,
        # 'dnrx4': 0.7,
        # 'dnrx5': 0.0,
        # 'dnrx6': -0.5,
        # 'dnrx7': -0.9,
        # 'dnrx8': -1.9,
        # 'dnsnr': 38.224999999999994,
        # 'dnsnr1': 38.9,
        # 'dnsnr2': 37.0,
        # 'dnsnr3': 36.3,
        # 'dnsnr4': 38.2,
        # 'dnsnr5': 39.3,
        # 'dnsnr6': 39.3,
        # 'dnsnr7': 38.9,
        # 'dnsnr8': 37.9,
        # 'upatt': 37.275,
        # 'upatt1': 37.0,
        # 'upatt10': 37.8,
        # 'upatt2': 37.3,
        # 'upatt3': 37.0,
        # 'upbw': 3.281854790508108,
        # 'upcorr': 0.0,
        # 'upcorr1': 0.0,
        # 'upcorr10': 0.0,
        # 'upcorr2': 0,
        # 'upcorr3': 0.0,
        # 'upfreq1': 57000000,
        # 'upfreq10': 25000000,
        # 'upfreq2': 37000000,
        # 'upfreq3': 44000000,
        # 'upko': 0.0,
        # 'upko1': 0.0,
        # 'upko10': 0.0,
        # 'upko2': 0,
        # 'upko3': 0.0,
        # 'upok': 100,
        # 'upsnr': 35.4,
        # 'upsnr1': 33.4,
        # 'upsnr10': 36.1,
        # 'upsnr2': 0.0,
        # 'upsnr3': 36.7,
        # 'uptx': 40.325,
        # 'uptx1': 40.0,
        # 'uptx10': 40.8,
        # 'uptx2': 40.3,
        # 'uptx3': 40.2
    }
    perf_defs=[
        # ('dnsnr', '.1f', 'dB', (45, 35), 0.5, 100),
        # ('uptx', '.1f', 'dBm', (58, 65), -2, +70),
        # ('dnrx', '.1f', 'dBm', (-20, -15, +15, +30), -50, +50),
        # ('too', 'd', 'Kg', (700, 1000), 0, 2000),
        # ('freq', 'd', 'Hz'),
        ('upsnr', '.1f', 'dB', (18, 10), 5, 90, [0.0]),
    ]
    perf_defs=[
        ('dnatt', '.1f', 'dB', [10,20,65,75], 0, 99),
        # ('dnrx', '.1f', 'dBm', [-25,-15,20,40], -50, +60),
        # ('dnsnr', '.1f', 'dB', [25,18], 4, 99),
        # ('dnfreq', 'd', 'Hz'),
    ]
    print process_raw_perfdata(tflk, perf_defs)


def test_process_perfdata():
    class Dummy(object):

        def __init__(self):
            self.sta_dntx_thresholds = '30,40'
            self.sta_dnrx_thresholds = '-50,-60'
            self.sta_dnsnr_thresholds = '40,30'
            self.sta_uptx_thresholds = '30,40'
            self.sta_uprx_thresholds = '-50,-60'
            self.sta_upsnr_thresholds = '40,30'
            self.sta_txlatency_thresholds = '10,20'
            self.sta_quality_thresholds = '90,80'
            self.sta_ccq_thresholds = '90,80'


    perfdata = "dntx=17dBm;30;40;-5;90 dnrx=-42dBm;-50;-60;-90;-30 dnsnr=54dB;40;30;5;90 uptx=17dBm;30;40;-5;90 uprx=-41dBm;-50;-60;-90;-30 upsnr=55dB;40;30;5;90"
    print 'p1', process_perfdata(Dummy(), perfdata, prefix='sta')
    perfdata = "dntx=-17dBm;30;40;-5;90 dnrx=-42dBm;-50;-60;-90;-30 dnsnr=54dB;40;30;5;90 uptx=17dBm;30;40;-5;90 uprx=-41dBm;-50;-60;-90;-30 upsnr=55dB;40;30;5;90"
    print 'p2', process_perfdata(Dummy(), perfdata, prefix='sta')
    perfdata = "dntx=100dBm;30;40;-5;90 dnrx=-42dBm;-50;-60;-90;-30 dnsnr=54dB;40;30;5;90 uptx=17dBm;30;40;-5;90 uprx=-41dBm;-50;-60;-90;-30 upsnr=55dB;40;30;5;90"
    print 'p3', process_perfdata(Dummy(), perfdata, prefix='sta')
    perfdata = "dntx=35dBm;30;40;-5;90 dnrx=-42dBm;-50;-60;-90;-30 dnsnr=54dB;40;30;5;90 uptx=17dBm;30;40;-5;90 uprx=-41dBm;-50;-60;-90;-30 upsnr=55dB;40;30;5;90"
    print 'p4', process_perfdata(Dummy(), perfdata, prefix='sta')
    perfdata = "dntx=45dBm;30;40;-5;90 dnrx=-42dBm;-50;-60;-90;-30 dnsnr=54dB;40;30;5;90 uptx=17dBm;30;40;-5;90 uprx=-41dBm;-50;-60;-90;-30 upsnr=55dB;40;30;5;90"
    print 'p5', process_perfdata(Dummy(), perfdata, prefix='sta')


if __name__ == '__main__':
    test_process_raw_perfdata()

