from osgeo import gdal

class GdalErrorHandler(object):
    def __init__(self):
        self.err_level = gdal.CE_None
        self.err_no = 0
        self.err_msg = ''

    def handler(self, err_level, err_no, err_msg):
        self.err_level = err_level
        self.err_no = err_no
        self.err_msg = err_msg

if __name__ == '__main__':
    err = GdalErrorHandler()
    gdal.PushErrorHandler(err.handler)
    gdal.UseExceptions()  # Exceptions will get raised on anything >= gdal.CE_Failure

    assert err.err_level == gdal.CE_None, 'the error level starts at 0'

    try:
        # Demonstrate handling of a warning message
        try:
            gdal.Error(gdal.CE_Warning, 8675309, 'Test warning message')
        except Exception:
            raise AssertionError('Operation raised an exception, this should not happen')
        else:
            assert err.err_level == gdal.CE_Warning, (
                'The handler error level should now be at warning')
            print('Handled error: level={}, no={}, msg={}'.format(
                err.err_level, err.err_no, err.err_msg))

        # Demonstrate handling of an error message
        try:
            gdal.Error(gdal.CE_Failure, 42, 'Test error message')
        except Exception as e:
            assert err.err_level == gdal.CE_Failure, (
                'The handler error level should now be at failure')
            assert err.err_msg == e.args[0], 'raised exception should contain the message'
            print('Handled warning: level={}, no={}, msg={}'.format(
                err.err_level, err.err_no, err.err_msg))
        else:
            raise AssertionError('Error message was not raised, this should not happen')

    finally:
        gdal.PopErrorHandler()