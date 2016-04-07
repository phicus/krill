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


def process_raw_perfdata(raw_data, perf_defs):

    def _check_value(warning, critical):
        # print '_check_value', warning, critical
        if float(warning) < float(critical):
            op_func, op_text = operator.gt, '>'
        else:
            op_func, op_text = operator.lt, '<'

        if critical and op_func(float(value), float(critical)):
            return (CRITICAL, '{metric}={value:{format}}{unit} {op_text} {critical:{format}}{unit}!!'.format(
                        metric=metric,
                        value=value,
                        format=format,
                        unit=unit,
                        op_text=op_text,
                        critical=critical
                    ))
        if warning and op_func(float(value), float(warning)):
            return (WARNING, '{metric}={value:{format}}{unit} {op_text} {warning:{format}}{unit}!'.format(
                        metric=metric,
                        value=value,
                        format=format,
                        unit=unit,
                        op_text=op_text,
                        warning=warning
                    ))
        return (OK, '{metric}={value:{format}}{unit}'.format(
                        metric=metric,
                        value=value,
                        format=format,
                        unit=unit,
                    ))

    checks = []
    perfs = []
    for pattern, format, unit, thresholds, min, max in perf_defs:
        if len(thresholds) == 2:
            warning, critical = thresholds
            low_critical = low_warning = None
        if len(thresholds) == 4:
            low_critical, low_warning, warning, critical = thresholds

        # print 'pattern, unit, warning, critical, min, max', pattern, unit, warning, critical, min, max
        for metric, value in raw_data.iteritems():
            if value is None:
                continue

            if re.match(r'%s(\d*)' % pattern, metric):
                try:
                    print 'process_raw_perfdata', metric, value, type(value), warning, critical, min, max, format, unit
                    perfs.append('{metric}={value:{format}}{unit};{warning:{format}};{critical:{format}};{min:{format}};{max:{format}}'.format(
                            metric=metric,
                            value=value,
                            warning=warning,
                            critical=critical,
                            min=min,
                            max=max,
                            format=format,
                            unit=unit,
                        ))
                except Exception, exc:
                    print 'process_raw_perfdata Exception', exc, metric, value, type(value), warning, critical, min, type(min), max, type(max), format, unit
                    # logger.warning("[KRILK] process_raw_perfdata Exception: (%s) %s %s %s %s %s %s %s %s %s %s %s", exc, metric, value, type(value), warning, critical, min, type(min), max, type(max), format, unit)


                if float(value) < float(min):
                    checks.append((UNKNOWN, '{metric}={value:{format}}{unit} below min({min}{unit})'.format(
                        metric=metric,
                        value=value,
                        min=min,
                        format=format,
                        unit=unit,
                    )))
                elif float(value) > float(max):
                    checks.append((UNKNOWN, '{metric}={value:{format}}{unit} above max({max}{unit})'.format(
                        metric=metric,
                        value=value,
                        max=max,
                        format=format,
                        unit=unit,
                    )))
                else:
                    checks.append(_check_value(warning, critical))
                    if low_critical and low_warning:
                        checks.append(_check_value(low_warning, low_critical))

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

        'dnrx': -18,
    }
    perf_defs=[
        ('dnsnr', '.1f', 'dB', (45, 35), 0.5, 100),
        ('uptx', '.1f', 'dBm', (58, 65), -2, +70),
        ('dnrx', '.1f', 'dBm', (-20, -15, +15, +30), -50, +50),
    ]
    print process_raw_perfdata(raw_data, perf_defs)


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

