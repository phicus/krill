import re
import operator
from shinken.misc.perfdata import Metric, PerfDatas

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


if __name__ == '__main__':

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
