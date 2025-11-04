#!/usr/bin/env node

import { spawn } from 'child_process';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

// Get the directory where this script is located
const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// Get the package root directory (parent of bin/)
const packageRoot = dirname(__dirname);

// Build the path to the Python module
const pythonModulePath = join(packageRoot, 'src', 'easy_jar_reader');

// Get command line arguments (skip first two: node and script path)
const args = process.argv.slice(2);

// Start the Python MCP server
const pythonProcess = spawn('python', ['-m', 'easy_jar_reader', ...args], {
  cwd: packageRoot,
  stdio: 'inherit',
  env: {
    ...process.env,
    PYTHONPATH: join(packageRoot, 'src')
  }
});

// Handle process termination
pythonProcess.on('exit', (code) => {
  process.exit(code || 0);
});

// Handle errors
pythonProcess.on('error', (err) => {
  console.error('Failed to start Easy JAR Reader MCP server:', err.message);
  console.error('\nPlease ensure:');
  console.error('1. Python 3.10 or higher is installed');
  console.error('2. Required dependencies are installed: pip install -e .');
  console.error('3. Java Development Kit (JDK) is installed for decompilation');
  process.exit(1);
});

// Handle Ctrl+C gracefully
process.on('SIGINT', () => {
  pythonProcess.kill('SIGINT');
});

process.on('SIGTERM', () => {
  pythonProcess.kill('SIGTERM');
});
