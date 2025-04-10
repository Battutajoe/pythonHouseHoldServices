const path = require('path');
const webpack = require('webpack');

module.exports = {
  // Entry point for your application
  entry: './src/index.js',

  // Output configuration
  output: {
    path: path.resolve(__dirname, 'dist'),
    filename: 'bundle.js',
    publicPath: '/',
  },

  // Module rules for processing different file types
  module: {
    rules: [
      {
        test: /\.js$/,
        exclude: /node_modules/,
        use: {
          loader: 'babel-loader',
          options: {
            presets: ['@babel/preset-env', '@babel/preset-react'],
          },
        },
      },
      {
        test: /\.css$/,
        use: ['style-loader', 'css-loader'],
      },
      {
        test: /\.(png|jpe?g|gif|svg)$/i,
        type: 'asset/resource', // Handle image files
      },
    ],
  },

  // Resolve configuration for handling Node.js globals
  resolve: {
    fallback: {
      process: require.resolve('process/browser'),
      buffer: require.resolve('buffer/'),
      util: require.resolve('util/'),
      stream: require.resolve('stream-browserify'),
      assert: require.resolve('assert/'),
      crypto: require.resolve('crypto-browserify'),
      http: require.resolve('stream-http'),
      https: require.resolve('https-browserify'),
      os: require.resolve('os-browserify/browser'),
      path: require.resolve('path-browserify'),
      zlib: require.resolve('browserify-zlib'), // Add zlib for compression support
      fs: false, // Disable fs module (not available in the browser)
    },
    extensions: ['.js', '.jsx'], // Add .jsx extension for React components
  },

  // Plugins for providing Node.js globals
  plugins: [
    new webpack.ProvidePlugin({
      process: 'process/browser',
      Buffer: ['buffer', 'Buffer'],
    }),
    new webpack.DefinePlugin({
      'process.env.NODE_ENV': JSON.stringify(process.env.NODE_ENV || 'development'), // Define environment variables
    }),
  ],

  // Enable source maps for debugging
  devtool: process.env.NODE_ENV === 'production' ? 'source-map' : 'eval-source-map',

  // Development server configuration
  devServer: {
    static: path.join(__dirname, 'dist'),
    hot: true,
    historyApiFallback: true,
    port: 3000, // Specify the port for the development server
    open: true, // Automatically open the browser
    client: {
      overlay: {
        errors: true,
        warnings: false,
      },
    },
  },

  // Performance hints (optional)
  performance: {
    hints: process.env.NODE_ENV === 'production' ? 'warning' : false, // Show performance hints in production
  },

  // Optimization for production builds
  optimization: {
    minimize: process.env.NODE_ENV === 'production', // Minimize code in production
    splitChunks: {
      chunks: 'all', // Split chunks for better caching
    },
  },
};