import {cloudEnvironment} from "./cloud-config";

App({
  onLaunch() {
    wx.cloud?.init({env: cloudEnvironment});
  },
});
