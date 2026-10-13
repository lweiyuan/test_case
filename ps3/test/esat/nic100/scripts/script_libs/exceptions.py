class BaseException(Exception):
    def __init__(self, msg):
        # from src.lib.log import logger_sys as logger
        # logger.error(msg)
        super(BaseException, self).__init__(msg)


class InvalidInputParam(BaseException):
    def __init__(self, msg):
        super(InvalidInputParam, self).__init__(msg)


class UnexpectedResult(BaseException):
    def __init__(self, msg):
        super(UnexpectedResult, self).__init__(msg)


class LowCliVersion(BaseException):
    def __init__(self, msg):
        super(LowCliVersion, self).__init__(msg)


class InvalidYAMLFormat(BaseException):
    def __init__(self, msg):
        super(InvalidYAMLFormat, self).__init__(msg)


class StepRuntimeError(BaseException):
    def __init__(self, msg):
        super(StepRuntimeError, self).__init__(msg)


class CaseRuntimeError(BaseException):
    def __init__(self, msg):
        super(CaseRuntimeError, self).__init__(msg)


class FuncExecuteError(BaseException):
    def __init__(self, msg):
        super(FuncExecuteError, self).__init__(msg)


class UnexpectEnvInfo(BaseException):
    def __init__(self, msg):
        super(UnexpectEnvInfo, self).__init__(msg)


class HttpResponseError(BaseException):
    def __init__(self, msg):
        super(HttpResponseError, self).__init__(msg)


class HttpRequestError(BaseException):
    def __init__(self, msg):
        super(HttpRequestError, self).__init__(msg)


class DatabaseError(BaseException):
    def __init__(self, msg):
        super(BaseException, self).__init__(msg)


class CMDResponseError(BaseException):
    def __init__(self, msg):
        super(BaseException, self).__init__(msg)


class UnexpectedError(BaseException):
    def __init__(self, msg):
        super(BaseException, self).__init__(msg)


class PerftestAnalysisError(BaseException):
    def __init__(self, msg):
        super(BaseException, self).__init__(msg)


class OpensmRunError(BaseException):
    def __init__(self, msg):
        super(BaseException, self).__init__(msg)


class TopoDataNoneError(BaseException):
    def __init__(self, msg):
        super(BaseException, self).__init__(msg)


class InitTopoError(BaseException):
    def __init__(self, msg):
        super(BaseException, self).__init__(msg)


class PerftestRuntimeError(BaseException):
    def __init__(self, msg):
        super(BaseException, self).__init__(msg)


class EnvError(BaseException):
    def __init__(self, msg):
        super(BaseException, self).__init__(msg)


class PerftestMonitorErr(BaseException):
    def __init__(self, msg):
        super(BaseException, self).__init__(msg)


class LinuxErrCode:
    def __new__(cls, value):
        if value == 1:
            return "[CMD Err] cmd run err"
        elif value == 2:
            return "[CMD Err] cmd param invalid"
        elif value == 126:
            return "[CMD Err] cmd has no permission to run"
        elif value == 127:
            return "[CMD Err] cannot find the cmd or path err"
        elif value == 130:
            return "[CMD Err] interrupt cmd run"
        else:
            return "[CMD Err] unknown err"
        # match value:
        #     case 1:
        #         return "[CMD Err] cmd run err"
        #     case 2:
        #         return "[CMD Err] cmd param invalid"
        #     case 126:
        #         return "[CMD Err] cmd has no permission to run"
        #     case 127:
        #         return "[CMD Err] cannot find the cmd or path err"
        #     case 130:
        #         return "[CMD Err] interrupt cmd run"
        #     case _:
        #         return "[CMD Err] unknown err"


class FlowingTopoError(BaseException):
    def __init__(self, msg):
        super(BaseException, self).__init__(msg)


class DataTypeError(BaseException):
    def __init__(self, msg):
        super(BaseException, self).__init__(msg)


class LidNumExceedError(BaseException):
    def __init__(self, msg):
        super(BaseException, self).__init__(msg)
