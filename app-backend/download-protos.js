#!/usr/bin/env node

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

// Paths for proto files and repositories
const SCRIPT_DIR = __dirname;
const COMMON_DIR = path.join(SCRIPT_DIR, 'common');
const PROTO_DIR = path.join(SCRIPT_DIR, 'riva/proto');

console.log('Proto file downloader script');
console.log(`Script directory: ${SCRIPT_DIR}`);
console.log(`Common repository target: ${COMMON_DIR}`);
console.log(`Proto files target: ${PROTO_DIR}`);

// Create directories if they don't exist
[COMMON_DIR, PROTO_DIR].forEach(dir => {
  if (!fs.existsSync(dir)) {
    console.log(`Creating directory: ${dir}`);
    fs.mkdirSync(dir, { recursive: true });
  }
});

// Function to download proto files from nvidia-riva/common repository
function downloadProtoFiles() {
  try {
    console.log('Checking for existing proto files...');
    
    // Check if proto directory already contains proto files
    if (fs.existsSync(path.join(PROTO_DIR, 'riva_asr.proto')) && 
        fs.existsSync(path.join(PROTO_DIR, 'riva_tts.proto'))) {
      console.log('Proto files already exist in proto directory, skipping download');
      return true;
    }
    
    // Check if common repository is already cloned
    const commonRepoExists = fs.existsSync(path.join(COMMON_DIR, '.git'));
    
    if (!commonRepoExists) {
      console.log('Cloning nvidia-riva/common repository...');
      execSync(`git clone https://github.com/nvidia-riva/common.git ${COMMON_DIR}`, {
        stdio: 'inherit'
      });
    } else {
      console.log('Common repository already exists, pulling latest changes...');
      execSync(`cd ${COMMON_DIR} && git pull`, {
        stdio: 'inherit'
      });
    }
    
    // Check if the riva/proto directory exists in the cloned repo
    const rivaProtoPath = path.join(COMMON_DIR, 'riva', 'proto');
    if (!fs.existsSync(rivaProtoPath)) {
      console.error(`Error: Expected directory not found: ${rivaProtoPath}`);
      return false;
    }
    
    // Copy proto files to our proto directory
    console.log('Copying proto files to proto directory...');
    const protoFiles = fs.readdirSync(rivaProtoPath);
    
    // Filter for relevant proto files (ASR and TTS)
    const relevantProtos = protoFiles.filter(file => 
      file.includes('riva_asr') || file.includes('riva_tts') || file.includes('riva_audio') || file.includes('riva_common')
    );
    
    if (relevantProtos.length === 0) {
      console.error('No relevant proto files found in the repository');
      return false;
    }
    
    // Copy each proto file
    relevantProtos.forEach(file => {
      const sourcePath = path.join(rivaProtoPath, file);
      const targetPath = path.join(PROTO_DIR, file);
      fs.copyFileSync(sourcePath, targetPath);
      console.log(`Copied: ${file}`);
    });
    
    console.log('Successfully downloaded and copied proto files');
    console.log('Available proto files:');
    fs.readdirSync(PROTO_DIR).forEach(file => {
      console.log(`- ${file}`);
    });
    
    return true;
  } catch (error) {
    console.error('Failed to download proto files:', error);
    return false;
  }
}

// Execute the download function
const success = downloadProtoFiles();

// Exit with appropriate code
process.exit(success ? 0 : 1); 