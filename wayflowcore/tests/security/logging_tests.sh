#!/bin/bash

# This cannot be tested in a pytest, which has its own rootLogger to communicate activity.
TESTS_DIR=$1

echo "#################################### LOGGER NULL TEST ######################################";

python $TESTS_DIR/check_rootLogger_handles_are_null.py
if [ $? -ne 0 ]; then
    echo "A StreamHandler was attached to the rootLogger on importing the automl package. FAILING Logging tests."; exit 1;
else
    echo "TEST PASSED."
fi

echo "#################################### UNDEFINED LOGGER TEST ######################################";

python $TESTS_DIR/check_undefined_logger.py
if [ $? -ne 0 ]; then
    echo "When application provides a loggingconfig, wayflowcore should not alter root loglevel instead it should use the application logger similar to how named loggers in the primary application behave"; exit 1;
else
    echo "TEST PASSED."
fi

echo "################################### LOGGER STREAM TEST #####################################";

# This test checks that wayflowcore logs always go to stdout unless the user specifies otherwise.
# The test also checks that some of the logs we expect to see during wayflowcore execution are indeed
# written to stdout.
# This test may fail if the logging behavior has changed (e.g. the log messages have been updated,
# or the logging stream has changed), or there are errors in the execution of wayflowcore

TMPDIR=$(mktemp -d /tmp/olwayflowcore.logstreamXXXXXXX)

logging_tests () {
    EXPECTED_LOGSTREAM=$1

    OUT_FILE=$TMPDIR/logging_stream.out;
    ERR_FILE=$TMPDIR/logging_stream.err;

    if [ "$EXPECTED_LOGSTREAM" == "stdout" ]; then
        EXPECTED_LOG_FILE=$OUT_FILE
        EXPECTED_EMPTY_FILE=$ERR_FILE
    else
        EXPECTED_LOG_FILE=$ERR_FILE
        EXPECTED_EMPTY_FILE=$OUT_FILE
    fi;

    python3 -c "
import wayflowcore
from wayflowcore.controlconnection import ControlFlowEdge
from wayflowcore.dataconnection import DataFlowEdge
from wayflowcore.flow import Flow
from wayflowcore.flowhelpers import create_single_step_flow
from wayflowcore.steps import (
    CompleteStep,
    FlowExecutionStep,
    InputMessageStep,
    OutputMessageStep,
    PromptExecutionStep,
    StartStep,
)
steps = {'output_step': OutputMessageStep('Hello!')}
flow = Flow(
    begin_step=steps['output_step'],
    steps=steps,
    transitions={'output_step': [None]},
)" >$OUT_FILE 2>$ERR_FILE

    declare -i LOGSTREAM_RESULT=0

    if [ $? -ne 0 ]; then
        echo "Script for stream checking failed... See output of the script below";
        LOGSTREAM_RESULT=1
    elif [ -s $EXPECTED_EMPTY_FILE ]; then
        LOGSTREAM_RESULT=1
        echo "Script wrote to unexpected output stream, when expected behaviour was to log to \
        $EXPECTED_LOGSTREAM given the logger initialization ($1).\
        Have you recently changed logging behaviour?";
        echo "Check stream outputs below for more info."
    else
        expected_logs=(
            "Usage of \`transitions\` is deprecated. Please use \`control_flow_edges\`."
        )

        for t in ${expected_logs[@]}; do
            grep -Fq "$t" $EXPECTED_LOG_FILE
            if [ $? -ne 0 ]; then
                echo "Script didn't write expected logs to $EXPECTED_LOGSTREAM: '$t'";
                echo "If the log messages have changed, update the expected_logs above, otherwise check\
                the stream outputs below for more info.";
                LOGSTREAM_RESULT=1
            fi;
        done;
    fi

    if [ $LOGSTREAM_RESULT -ne 0 ]; then
        RESULT=1
        echo "##### WayFlow wrote the following to stderr #####"
        cat $ERR_FILE
        echo "##### WayFlow wrote the following to stdout #####"
        cat $OUT_FILE
        rm $OUT_FILE $ERR_FILE
        echo "LOGGING Stream test failed. Failing logging tests."; exit 1;
    else
        echo "TEST PASSED.";
    fi;

    rm $OUT_FILE $ERR_FILE
}

echo "######### Logtest with stderr ########"
logging_tests "stderr"
