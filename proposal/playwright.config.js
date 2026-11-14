import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./tests',testMatch:'*.browser.js',workers:1,use:{baseURL:'http://127.0.0.1:3001',headless:true,launchOptions:{executablePath:'/usr/bin/chromium',args:['--no-sandbox']}}});
