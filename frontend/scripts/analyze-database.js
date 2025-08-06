const { Client } = require('pg');

// Database connection configuration
const dbConfig = {
  host: 'localhost',
  port: 5432,
  database: 'ddf_db', // Based on docker-compose configuration
  user: 'ddf_user',
  password: 'ddf_password',
  connectTimeout: 10000,
};

// Alternative config if the database name is different
const altDbConfig = {
  host: 'localhost',
  port: 5432,
  database: 'traffic_db', // As requested by user
  user: 'ddf_user',
  password: 'ddf_password',
  connectTimeout: 10000,
};

async function connectToDatabase() {
  let client = new Client(dbConfig);
  
  try {
    console.log('Attempting to connect to ddf_db...');
    await client.connect();
    console.log('✅ Successfully connected to PostgreSQL database: ddf_db');
    return client;
  } catch (error) {
    console.log('❌ Failed to connect to ddf_db, trying traffic_db...');
    await client.end();
    
    client = new Client(altDbConfig);
    try {
      await client.connect();
      console.log('✅ Successfully connected to PostgreSQL database: traffic_db');
      return client;
    } catch (altError) {
      console.error('❌ Failed to connect to both databases:');
      console.error('ddf_db error:', error.message);
      console.error('traffic_db error:', altError.message);
      throw altError;
    }
  }
}

async function runQuery(client, queryName, query) {
  try {
    console.log(`\n📊 Running query: ${queryName}`);
    console.log('='.repeat(50));
    
    const result = await client.query(query);
    
    if (result.rows.length === 0) {
      console.log('No data found.');
      return;
    }
    
    // Print column headers
    const columns = Object.keys(result.rows[0]);
    console.log(columns.join(' | '));
    console.log('-'.repeat(columns.join(' | ').length));
    
    // Print rows (limit to first 20 for readability)
    const displayRows = result.rows.slice(0, 20);
    displayRows.forEach(row => {
      const values = columns.map(col => {
        const val = row[col];
        if (val === null) return 'NULL';
        if (typeof val === 'string') return val.substring(0, 30);
        if (val instanceof Date) return val.toISOString().substring(0, 19);
        return String(val);
      });
      console.log(values.join(' | '));
    });
    
    if (result.rows.length > 20) {
      console.log(`... and ${result.rows.length - 20} more rows`);
    }
    
    console.log(`\nTotal rows: ${result.rows.length}`);
    
  } catch (error) {
    console.error(`❌ Error running query "${queryName}":`, error.message);
  }
}

async function analyzeDatabase() {
  let client;
  
  try {
    client = await connectToDatabase();
    
    // 1. Basic data overview
    console.log('\n🔍 ANALYZING REAL TRAFFIC DATA (EXCLUDING DRT PREDICTIONS)');
    console.log('=' .repeat(60));
    
    // Check table existence and record counts
    await runQuery(client, 'Table Record Counts', `
      SELECT 
        'stop_usage' as table_name, 
        COUNT(*) as record_count,
        'Real bus boarding/alighting data' as description
      FROM stop_usage
      UNION ALL
      SELECT 
        'bus_stops' as table_name, 
        COUNT(*) as record_count,
        'Bus stop locations and info' as description
      FROM bus_stops
      UNION ALL
      SELECT 
        'bus_routes' as table_name, 
        COUNT(*) as record_count,
        'Bus route information' as description
      FROM bus_routes
      UNION ALL
      SELECT 
        'route_stops' as table_name, 
        COUNT(*) as record_count,
        'Route-stop mapping' as description
      FROM route_stops;
    `);
    
    // 2. Date range for stop_usage (actual traffic data)
    await runQuery(client, 'Stop Usage Data Date Range', `
      SELECT 
        MIN(recorded_at::date) as start_date,
        MAX(recorded_at::date) as end_date,
        COUNT(DISTINCT recorded_at::date) as total_days,
        COUNT(*) as total_records,
        COUNT(DISTINCT stop_id) as unique_stops_with_data
      FROM stop_usage;
    `);
    
    // 3. Bus stops table information
    await runQuery(client, 'Bus Stops Overview', `
      SELECT 
        COUNT(*) as total_stops,
        COUNT(CASE WHEN is_active = true THEN 1 END) as active_stops,
        COUNT(CASE WHEN latitude IS NOT NULL AND longitude IS NOT NULL THEN 1 END) as stops_with_coordinates,
        COUNT(DISTINCT district) as unique_districts,
        STRING_AGG(DISTINCT district, ', ') as districts
      FROM bus_stops;
    `);
    
    // 4. Bus routes table information
    await runQuery(client, 'Bus Routes Overview', `
      SELECT 
        COUNT(*) as total_routes,
        COUNT(CASE WHEN is_active = true THEN 1 END) as active_routes,
        COUNT(DISTINCT route_type) as route_types,
        STRING_AGG(DISTINCT route_type, ', ') as types,
        AVG(weekday_interval) as avg_weekday_interval_minutes,
        AVG(saturday_interval) as avg_saturday_interval_minutes,
        AVG(sunday_interval) as avg_sunday_interval_minutes
      FROM bus_routes;
    `);
    
    // 5. Stop usage data quality and patterns
    await runQuery(client, 'Stop Usage Data Quality', `
      SELECT 
        COUNT(*) as total_records,
        COUNT(CASE WHEN is_operational = true THEN 1 END) as operational_records,
        COUNT(CASE WHEN is_operational = false THEN 1 END) as non_operational_records,
        ROUND(COUNT(CASE WHEN is_operational = true THEN 1 END) * 100.0 / COUNT(*), 2) as operational_percentage,
        SUM(boarding_count) as total_boarding,
        SUM(alighting_count) as total_alighting,
        ROUND(AVG(boarding_count), 2) as avg_boarding_per_record,
        ROUND(AVG(alighting_count), 2) as avg_alighting_per_record
      FROM stop_usage;
    `);
    
    // 6. Daily traffic patterns
    await runQuery(client, 'Daily Traffic Summary (Last 14 days)', `
      SELECT 
        recorded_at::date as date,
        COUNT(DISTINCT stop_id) as active_stops,
        SUM(boarding_count) as total_boarding,
        SUM(alighting_count) as total_alighting,
        SUM(boarding_count + alighting_count) as total_passengers,
        COUNT(CASE WHEN is_operational = true THEN 1 END) as operational_records,
        ROUND(AVG(boarding_count + alighting_count), 2) as avg_passengers_per_record
      FROM stop_usage
      WHERE recorded_at >= CURRENT_DATE - INTERVAL '14 days'
      GROUP BY recorded_at::date
      ORDER BY recorded_at::date DESC;
    `);
    
    // 7. Hourly traffic patterns
    await runQuery(client, 'Hourly Traffic Patterns (Operational Hours Only)', `
      SELECT 
        EXTRACT(hour FROM recorded_at) as hour,
        COUNT(*) as total_records,
        COUNT(DISTINCT stop_id) as active_stops,
        SUM(boarding_count) as total_boarding,
        SUM(alighting_count) as total_alighting,
        ROUND(AVG(boarding_count), 2) as avg_boarding,
        ROUND(AVG(alighting_count), 2) as avg_alighting
      FROM stop_usage
      WHERE is_operational = true
      GROUP BY EXTRACT(hour FROM recorded_at)
      ORDER BY hour;
    `);
    
    // 8. Top 10 busiest stops
    await runQuery(client, 'Top 10 Busiest Bus Stops (All Time)', `
      SELECT 
        s.stop_name,
        s.stop_number,
        s.district,
        SUM(su.boarding_count) as total_boarding,
        SUM(su.alighting_count) as total_alighting,
        SUM(su.boarding_count + su.alighting_count) as total_passengers,
        COUNT(CASE WHEN su.is_operational = true THEN 1 END) as operational_hours,
        ROUND(AVG(su.boarding_count + su.alighting_count), 2) as avg_passengers_per_hour
      FROM stop_usage su
      JOIN bus_stops s ON su.stop_id = s.stop_id
      WHERE su.is_operational = true
      GROUP BY s.stop_id, s.stop_name, s.stop_number, s.district
      ORDER BY total_passengers DESC
      LIMIT 10;
    `);
    
    // 9. Route utilization
    await runQuery(client, 'Route Utilization Summary', `
      SELECT 
        br.route_number,
        br.route_type,
        br.start_point,
        br.end_point,
        COUNT(DISTINCT rs.stop_id) as total_stops_in_route,
        COALESCE(SUM(su.boarding_count), 0) as total_boarding,
        COALESCE(SUM(su.alighting_count), 0) as total_alighting,
        COALESCE(ROUND(AVG(su.boarding_count + su.alighting_count), 2), 0) as avg_passengers_per_stop_hour
      FROM bus_routes br
      JOIN route_stops rs ON br.route_id = rs.route_id
      LEFT JOIN stop_usage su ON rs.stop_id = su.stop_id AND su.is_operational = true
      WHERE br.is_active = true
      GROUP BY br.route_id, br.route_number, br.route_type, br.start_point, br.end_point
      ORDER BY total_boarding DESC;
    `);
    
    // 10. Weekend vs Weekday patterns
    await runQuery(client, 'Weekend vs Weekday Traffic Patterns', `
      SELECT 
        CASE 
          WHEN is_weekend = true THEN 'Weekend'
          ELSE 'Weekday'
        END as day_type,
        COUNT(*) as total_records,
        COUNT(DISTINCT stop_id) as unique_stops,
        SUM(boarding_count) as total_boarding,
        SUM(alighting_count) as total_alighting,
        ROUND(AVG(boarding_count), 2) as avg_boarding_per_record,
        ROUND(AVG(alighting_count), 2) as avg_alighting_per_record
      FROM stop_usage
      WHERE is_operational = true
      GROUP BY is_weekend
      ORDER BY is_weekend;
    `);
    
    console.log('\n✅ Database analysis completed successfully!');
    console.log('\n📋 SUMMARY:');
    console.log('- This analysis covers REAL operational traffic data only');
    console.log('- stop_usage: Actual bus boarding/alighting records');
    console.log('- bus_stops: Physical bus stop locations and information');
    console.log('- bus_routes: Bus route definitions and schedules');
    console.log('- route_stops: Mapping between routes and stops');
    console.log('- No DRT prediction data was included in this analysis');
    
  } catch (error) {
    console.error('❌ Database analysis failed:', error.message);
    process.exit(1);
  } finally {
    if (client) {
      await client.end();
      console.log('\n🔌 Database connection closed.');
    }
  }
}

// Run the analysis
if (require.main === module) {
  analyzeDatabase().catch(console.error);
}

module.exports = { analyzeDatabase };