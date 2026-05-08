# Optimization Checklist

Use this before each YuanXiao delivery.

1. Check Android UI rendering, memory caps, image compression, Markdown/table
   rendering, and notification behavior.
2. Check polling paths: inbox, dashboard, and session history should fetch only
   missing information whenever possible.
3. Check bridge/server file scans, timeouts, log retention, and request limits.
4. Bump version and keep APK names as `yuanxiao-<version>.apk`.
5. Build and signature-verify the APK.
6. Smoke-test the touched public route using the private relay config.
7. Upload the APK to the existing Quark `元宵` folder when doing a full delivery.
8. Commit and push the GitHub repo.
9. Send the Feishu/Yutu completion reminder for full delivery workflows.
