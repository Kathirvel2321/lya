"""Offline regression checks. Fake secrets, temporary stores, no camera/network."""
import ast
import importlib
import os
from pathlib import Path
import sys
import tempfile
import threading
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parent


def function(path,name):
    tree=ast.parse((ROOT/path).read_text(encoding="utf-8-sig"))
    return compile(ast.Module(body=[n for n in tree.body if isinstance(n,(ast.FunctionDef,ast.ClassDef)) and n.name==name],type_ignores=[]),str(path),"exec")


class Foundations(unittest.TestCase):
    def test_policy_denies_unknown_roles_and_actions(self):
        from security.policy import Session,allowed
        for role in (None,"unknown","stranger","friend","secondary"):
            self.assertFalse(allowed(Session(role=role),"vault",True))
            self.assertFalse(allowed(Session(role=role),"theme_apply",True))
        self.assertFalse(allowed(Session(role="admin"),"vault"))
        self.assertTrue(allowed(Session(role="admin"),"vault",True))
        self.assertFalse(allowed(Session(role="admin"),"execute_generated_python",True))
        self.assertTrue(allowed(Session(role="friend"),"open_app"))

    def test_guest_context_never_reads_private_memory_or_owner_history(self):
        captured=[]
        def private():raise AssertionError("guest read private memory")
        ns={"_memory_block":private,"detect_tone":lambda _:"neutral",
            "SYSTEM":"{name}: {memory}","_histories":{("owner",True):[{"role":"assistant","content":"SECRET"}]},
            "_chat":lambda m:captured.append(m) or "reply","set_tone":lambda _:None}
        exec(function(Path("brain/mind.py"),"reply"),ns)
        ns["reply"]("hi",session_id="guest",verified=False)
        ns["reply"]("hi again",session_id="guest2",verified=False)
        self.assertNotIn("SECRET",str(captured))
        self.assertEqual(len(captured[1]),2)
        self.assertIn(("guest",False),ns["_histories"])

    def test_face_template_decodes_saved_float32(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as tmp:
            store=Path(tmp)/"face";store.write_bytes(b"placeholder")
            raw=np.full((128,128),0.2,dtype=np.float32)
            ns={"os":os,"np":np,"STORE":str(store),"vault":types.SimpleNamespace(decrypt_file=lambda _:raw.tobytes()),
                "_face_vector_from_jpg":lambda _:raw}
            exec(function(Path("vision/face_auth.py"),"verify_from_jpg"),ns)
            self.assertTrue(ns["verify_from_jpg"](b"fake")[0])

    def test_folder_paging_and_scope(self):
        from skills.files import FolderBrowser
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)/"scope";root.mkdir()
            for i in range(7):(root/f"folder{i}").mkdir()
            (root/"script.py").write_text("raise RuntimeError('must never run')")
            browser=FolderBrowser(root,page_size=3)
            data=browser.listing();self.assertEqual(len(data["entries"]),3);self.assertTrue(data["more"])
            browser.scroll(1);self.assertEqual(browser.page,1)
            with self.assertRaises((ValueError,PermissionError)):browser.open("../../")
            with self.assertRaises(PermissionError):browser._inside(root.parent)
            browser.back();self.assertEqual(browser.current,root)
            browser.page=0;browser.page_size=20;browser.listing()
            detail=browser.open("script.py");self.assertEqual(detail["file"],"script.py")

    def test_themes_validate_and_undo_without_code(self):
        from ui import themes
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/"theme.json"
            themes.save("halo",path);themes.save("pulse",path)
            self.assertEqual(themes.undo(path)["theme"],"halo")
            before=path.read_bytes()
            with self.assertRaises(ValueError):themes.save("__import__('os')",path)
            self.assertEqual(path.read_bytes(),before)

    def test_memory_parallel_roundtrip_and_corrupt_store_preserved(self):
        from cryptography.fernet import Fernet
        f=Fernet(Fernet.generate_key())
        fake=types.ModuleType("security.vault")
        fake.encrypt=f.encrypt;fake.decrypt=f.decrypt
        fake.encrypt_text=lambda s:f.encrypt(s.encode()).decode()
        fake.decrypt_text=lambda s:f.decrypt(s.encode()).decode()
        # Import only against a test vault; no DPAPI key is created or read.
        with patch.dict(sys.modules,{"security.vault":fake}):
            import security
            with patch.object(security,"vault",fake,create=True):
                db=importlib.import_module("security.database")
                mem=importlib.import_module("brain.memory")
                with tempfile.TemporaryDirectory() as tmp,patch.object(db,"vault",fake),patch.object(mem,"vault",fake),patch.object(mem,"DB",str(Path(tmp)/"brain.db")):
                    errors=[]
                    def write(i):
                        try:mem.remember("fact",f"key{i}",f"secret-{i}")
                        except Exception as e:errors.append(e)
                    threads=[threading.Thread(target=write,args=(i,)) for i in range(8)]
                    for t in threads:t.start()
                    for t in threads:t.join()
                    self.assertEqual(errors,[])
                    self.assertEqual(len(mem.recall(limit=20)),8)
                    path=Path(mem.DB+".lya")
                    self.assertNotIn(b"secret-",path.read_bytes())
                    self.assertFalse(Path(mem.DB+".working").exists())
                    self.assertEqual(mem.forget_exact("key1"),1)
                    path.write_bytes(b"corrupt")
                    with self.assertRaises(Exception):mem.remember("fact","new","new")
                    self.assertEqual(path.read_bytes(),b"corrupt")
                sys.modules.pop("brain.memory",None)
                sys.modules.pop("security.database",None)

    def test_build_mode_never_accesses_device_or_memory(self):
        from main import Assistant
        face=types.SimpleNamespace(show_folders=lambda d:None,apply_theme=lambda n:None)
        app=Assistant.__new__(Assistant);app.face=face;app.build=True
        self.assertIn("no device access",app.handle("open calculator"))
        self.assertIn("no device access",app.handle("remember my password"))
        app.handle("show folders")
        self.assertIn("Preview",app.handle("use theme halo"))

    def test_denied_theme_does_not_write_settings(self):
        from main import Assistant
        from security.policy import Session
        app=Assistant.__new__(Assistant);app.build=False;app.session=Session();app.identify=lambda:None
        app.permit=lambda *a:False
        with patch("ui.themes.save",side_effect=AssertionError("unexpected write")):
            self.assertIn("no action",app.handle("use theme halo"))

    def test_cancel_discards_queued_actions_and_browse_authority(self):
        from main import Assistant
        import queue
        app=Assistant.__new__(Assistant)
        app.cancelled=threading.Event();app.generation=0;app.commands=queue.Queue()
        app.commands.put((0,"open calculator"));app.browser=object();app.browse_until=99999
        app.pending_lesson="draft"
        app.face=types.SimpleNamespace(close_panel=lambda:None,set_state=lambda _:None)
        app.submit("stop")
        self.assertTrue(app.cancelled.is_set());self.assertTrue(app.commands.empty())
        self.assertIsNone(app.browser);self.assertEqual(app.browse_until,0)

    def test_generated_code_activation_never_imports(self):
        ns={};exec(function(Path("skills/forge.py"),"activate"),ns)
        self.assertIn("disabled",ns["activate"]())

    def test_gateway_blocks_token_only_enrollment(self):
        import json
        import io
        ns={"BaseHTTPRequestHandler":object,"parse_qs":__import__('urllib.parse',fromlist=['parse_qs']).parse_qs,"json":json}
        exec(function(Path("web_server.py"),"Handler"),ns)
        h=ns["Handler"]();h.path="/enroll_face"
        payload=b"token=fake&frames=fake"
        h.headers={"Content-Length":str(len(payload))};h.rfile=io.BytesIO(payload)
        h._check_token=lambda _:True
        sent=[];h._send=lambda *args:sent.append(args)
        h.do_POST();self.assertEqual(sent[0][0],403)


    def test_phone_approval_is_bound_to_displayed_task_and_cannot_replay(self):
        import json
        import time
        import secrets
        from cryptography.fernet import Fernet
        f=Fernet(Fernet.generate_key())
        with tempfile.TemporaryDirectory() as tmp:
            ns={"os":os,"json":json,"time":time,"secrets":secrets,
                "vault":types.SimpleNamespace(encrypt=f.encrypt,decrypt=f.decrypt),
                "GRANT_FILE":str(Path(tmp)/"grant"),"CHALLENGE_FILE":str(Path(tmp)/"challenge"),
                "_NONCE":"task-a","GRANT_TTL":120,"POLL_SECONDS":45}
            for name in ("_write_challenge","current_challenge","phone_approve","_consume_phone_grant"):
                exec(function(Path("security/escalation.py"),name),ns)
            ns["_write_challenge"]("task-a","Read Documents for five minutes")
            self.assertEqual(ns["current_challenge"]()["task"],"Read Documents for five minutes")
            ns["phone_approve"]("task-b")
            self.assertFalse(ns["_consume_phone_grant"]())
            ns["phone_approve"]("task-a")
            self.assertTrue(ns["_consume_phone_grant"]())
            self.assertFalse(ns["_consume_phone_grant"]())
            ns["_NONCE"]=None
            ns["phone_approve"]("task-a")
            self.assertFalse(ns["_consume_phone_grant"]())

    def test_missing_liveness_model_denies(self):
        ns={"_get_face_checker":lambda:None}
        exec(function(Path("security/liveness.py"),"face_liveness"),ns)
        self.assertFalse(ns["face_liveness"](b"image")[0])

    def test_plain_http_cannot_issue_phone_approval(self):
        import json,io
        ns={"BaseHTTPRequestHandler":object,"parse_qs":__import__('urllib.parse',fromlist=['parse_qs']).parse_qs,"json":json}
        exec(function(Path("web_server.py"),"Handler"),ns)
        h=ns["Handler"]();h.path="/escalate";payload=b"token=fake&nonce=test"
        h.headers={"Content-Length":str(len(payload))};h.rfile=io.BytesIO(payload)
        h.connection=object();h._check_token=lambda _:True
        sent=[];h._send=lambda *args:sent.append(args)
        h.do_POST();self.assertEqual(sent[0][0],403)
        self.assertIn("HTTPS",sent[0][1])


if __name__=="__main__":unittest.main(verbosity=2)
