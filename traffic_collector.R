library(hereR)
library(sf)
library(lubridate)
# Semarang

# Set your API key
set_key("iEMGp8CIQbV4hUvjqAqgt0ThgxAQduV2sZ8LtiglPKg")

# Function to collect traffic data
collect_traffic_data_smg <- function() {
  # Set timezone to GMT+7
  Sys.setenv(TZ="Asia/Bangkok")
  # Define your area of interest (bbox or polygon)
  # Example bbox for downtown Semarang
  bbox_smg <- st_bbox(c(xmin = 110.227,
                    ymin = -7.105,
                    xmax = 110.528,
                    ymax = -6.919))

  # Convert bbox to sf polygon with CRS
  aoi_smg <- st_as_sfc(bbox_smg) %>%
         st_set_crs(4326)  # WGS84 coordinate system

  # Set current timestamp
  # Set current timestamp in GMT+7
  current_time <- with_tz(Sys.time(), "Asia/Bangkok")
  timestamp <- format(current_time, "%Y%m%d_%H%M%S")
  tryCatch({
    # Get traffic flow data
    traffic_data_smg <- flow(
      aoi_smg,
      # Include more road types (ranges from 1-4, where 1 is major highways and 4 includes local streets)
      # Increase length of road segments covered
      #length = 100000,
      # Get data for more roads
      #limit = 10000
    )

    # Add timestamp column
    traffic_data_smg$timestamp <- Sys.time()

    # Create output directory if it doesn't exist
    dir.create("traffic_data_smg", showWarnings = FALSE)

    # Save as GeoPackage
    st_write(traffic_data_smg,
             dsn = paste0("traffic_data_smg/semarang_traffic_", timestamp, ".gpkg"),
             driver = "GPKG",
             append = FALSE)

    cat(sprintf("Data collected successfully at %s\n", Sys.time()))

    # Return the data
    return(traffic_data_smg)

  }, error = function(e) {
    cat(sprintf("Error collecting data at %s: %s\n", Sys.time(), e$message))
    return(NULL)
  })
}

# Run collection
traffic_data_smg <- collect_traffic_data_smg()

# Optional: View the first few rows of the data
if (!is.null(traffic_data_smg)) {
  print(head(traffic_data_smg))
}

# Bandung

# Function to collect traffic data
collect_traffic_data_bdg <- function() {
  # Set timezone to GMT+7
  Sys.setenv(TZ="Asia/Bangkok")
  # Define your area of interest (bbox or polygon)
  # Example bbox for downtown Semarang
  bbox_bdg <- st_bbox(c(xmin = 107.4688,
                    ymin = -7.0848,
                    xmax = 107.8261,
                    ymax = -6.8294))

  # Convert bbox to sf polygon with CRS
  aoi_bdg <- st_as_sfc(bbox_bdg) %>%
         st_set_crs(4326)  # WGS84 coordinate system

  # Set current timestamp
  # Set current timestamp in GMT+7
  current_time <- with_tz(Sys.time(), "Asia/Bangkok")
  timestamp <- format(current_time, "%Y%m%d_%H%M%S")
  tryCatch({
    # Get traffic flow data
    traffic_data_bdg <- flow(
      aoi_bdg,
      # Include more road types (ranges from 1-4, where 1 is major highways and 4 includes local streets)
      # Increase length of road segments covered
      #length = 100000,
      # Get data for more roads
      #limit = 10000
    )

    # Add timestamp column
    traffic_data_bdg$timestamp <- Sys.time()

    # Create output directory if it doesn't exist
    dir.create("traffic_data_bdg", showWarnings = FALSE)

    # Save as GeoPackage
    st_write(traffic_data_bdg,
             dsn = paste0("traffic_data_bdg/bandung_traffic_", timestamp, ".gpkg"),
             driver = "GPKG",
             append = FALSE)

    cat(sprintf("Data collected successfully at %s\n", Sys.time()))

    # Return the data
    return(traffic_data_bdg)

  }, error = function(e) {
    cat(sprintf("Error collecting data at %s: %s\n", Sys.time(), e$message))
    return(NULL)
  })
}

# Run collection
traffic_data_bdg <- collect_traffic_data_bdg()

# Optional: View the first few rows of the data
if (!is.null(traffic_data_bdg)) {
  print(head(traffic_data_bdg))
}

# Jakarta

# Function to collect traffic data
collect_traffic_data_jkt <- function() {
  # Set timezone to GMT+7
  Sys.setenv(TZ="Asia/Bangkok")
  # Define your area of interest (bbox or polygon)
  # Example bbox for Jakarta
  bbox_jkt <- st_bbox(c(xmin = 106.6036,
                    ymin = -6.4096,
                    xmax = 107.11,
                    ymax = -6.0911))

  # Convert bbox to sf polygon with CRS
  aoi_jkt <- st_as_sfc(bbox_jkt) %>%
         st_set_crs(4326)  # WGS84 coordinate system

  # Set current timestamp
  # Set current timestamp in GMT+7
  current_time <- with_tz(Sys.time(), "Asia/Bangkok")
  timestamp <- format(current_time, "%Y%m%d_%H%M%S")
  tryCatch({
    # Get traffic flow data
    traffic_data_jkt <- flow(
      aoi_jkt,
      # Include more road types (ranges from 1-4, where 1 is major highways and 4 includes local streets)
      # Increase length of road segments covered
      #length = 100000,
      # Get data for more roads
      #limit = 10000
    )

    # Add timestamp column
    traffic_data_jkt$timestamp <- Sys.time()

    # Create output directory if it doesn't exist
    dir.create("traffic_data_jkt", showWarnings = FALSE)

    # Save as GeoPackage
    st_write(traffic_data_jkt,
             dsn = paste0("traffic_data_jkt/jakarta_traffic_", timestamp, ".gpkg"),
             driver = "GPKG",
             append = FALSE)

    cat(sprintf("Data collected successfully at %s\n", Sys.time()))

    # Return the data
    return(traffic_data_jkt)

  }, error = function(e) {
    cat(sprintf("Error collecting data at %s: %s\n", Sys.time(), e$message))
    return(NULL)
  })
}

# Run collection
traffic_data_jkt <- collect_traffic_data_jkt()

# Optional: View the first few rows of the data
if (!is.null(traffic_data_jkt)) {
  print(head(traffic_data_jkt))
}
