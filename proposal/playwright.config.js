import {defineConfig} from '@playwright/test';
export default defineConfig({testDir:'./tests',testMatch:'*.browser.js',workers:1,webServer:{command:'npm run dev',url:'http://127.0.0.1:3001',reuseExistingServer:true,timeout:20000},use:{baseURL:'http://127.0.0.1:3001',headless:true,launchOptions:{executablePath:'/usr/bin/chromium',args:['--no-sandbox']}}});
