import importlib.util as u, sys, site
print("exe", sys.executable)
print("user_site", site.ENABLE_USER_SITE)
print("dvc", bool(u.find_spec("dvc")), "mlflow", bool(u.find_spec("mlflow")))
print([p for p in sys.path if "site-packages" in p][:3])
