$IMAGE = "asia-east2-docker.pkg.dev/secret-medium-491502-n8/cloud-run-source-deploy/quant-api@sha256:3d3f4b69a3de03471e143aa88903c5484087e79fbc2124a8c32eb5e305138463"

gcloud run jobs create quant-sync-t212 `
  --image $IMAGE `
  --region asia-east2 `
  --task-timeout 120s `
  --max-retries 1 `
  --set-secrets "DATABASE_URL_OVERRIDE=DATABASE_URL:latest,T212_API_KEY=T212_API_KEY:latest,T212_API_SECRET=T212_API_SECRET:latest" `
  --set-env-vars "APP_ENV=production,PYTHONPATH=/app" `
  --command "python,-m,apps.cli.main,sync-trading212,--no-demo" `
  --memory 512Mi
