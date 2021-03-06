# OpenEIS Configuration Files


## Introduction

A configuration file describes parameters needed to run an application from the [command line](command_line_basics_unix.md).
The configuration file provides the application with the same information that would be collected by the graphical user interface.
You can also run the application on the configuration file through the [API](server_api_pages.md).

*TODO: Add appropriate link to running application through GUI, once available in user documentation.*


## Configuration file structure

A configuration file has the following structure:

    [global_settings]
    application=daily_summary
    dataset_id=4
    sensormap_id=4

    [application_config]
    building_sq_ft=3000
    building_name="bldg90"

    [inputs]
    load=lbnl/bldg90/WholeBuildingElectricity

(This example happens to come from file `openeis/applications/utest_applications/utest_daily_summary/daily_summary_floats.ini`.)


## [global settings]

The `[global settings]` section includes:

+ `application`
  The name of the application to run.
+ `dataset_id`
  The dataset to use from the database.
+ `sensormap_id`
  The sensor map to use from the database.

The `dataset_id` and `sensormap_id` are numbered starting from 1.
To inspect the current database for valid numbers, use the [server API](server_api_pages.md).


## [application_config]

The `application_config` section lists all configuration parameters needed for an application.
The keys correspond to the keys in the dictionary returned by an application's `get_config_parameters()` method.


## [inputs]

The `inputs` section identifies the data to use when running the application.
The keys correspond to the keys in the dictionary returned by an application's `required_input()` method.

For example in the file above, the input has something representing at path to the required sensor input.
The path is always `site/building/SensorName`.

*TODO: Add a section documenting means of forming a valid configuration file based on information that can be extracted from the GUI.*
