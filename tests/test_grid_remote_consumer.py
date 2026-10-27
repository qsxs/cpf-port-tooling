"""提交门禁内的最小 HTTP/来源/环境语义测试；不发网络或运行 Gradle。"""
import contextlib
import importlib.util
import io
from http.client import IncompleteRead
import json
import os
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('grid_remote', ROOT/'scripts/grid_remote_consumer.py')
consumer = importlib.util.module_from_spec(spec)
spec.loader.exec_module(consumer)
VERSION = '2.8.0-cpf11-preview-ed3472803fdb-40432726650-1'
SHA = 'ed3472803fdb637d601391f62f43aba1bfea551f'


def klib(target=None):
    stream=io.BytesIO()
    with zipfile.ZipFile(stream,'w') as archive:
        prefix='' if target else 'commonMain/'
        archive.writestr(prefix+'default/manifest','native_targets='+target if target else 'unique_name=TEST_ONLY_METADATA')
        archive.writestr(prefix+'default/linkdata/module',b'TEST_ONLY_METADATA')
        if target:archive.writestr('default/ir/body',b'TEST_ONLY_IR')
    return stream.getvalue()


class RemoteConsumerTest(unittest.TestCase):
    def setUp(self):
        local=ROOT/'.local';local.mkdir(exist_ok=True)
        self.output=Path(tempfile.mkdtemp(prefix='consumer-check-',dir=local))
        self.root_url=consumer.PAGES+consumer.GROUP.replace('.','/')+'/grid/'+VERSION+'/grid-'+VERSION+'.module'
        self.responses={};self.urls=[]
        root={'component':{'group':consumer.GROUP,'module':'grid','version':VERSION},'variants':[]}
        def artifact(module,url,data):
            self.responses[url]=data
            return {'name':module,'url':url.rsplit('/',1)[1],'size':len(data),'sha256':consumer.digest(data)}
        metadata_url=self.root_url.rsplit('/',1)[0]+'/grid-'+VERSION+'.jar'
        root['variants'].append({'name':'metadata','attributes':{'org.gradle.usage':'kotlin-metadata','org.jetbrains.kotlin.platform.type':'common','org.gradle.category':'library'},'files':[artifact('metadata',metadata_url,klib())]})
        for target,module in [('ohos_x64','grid-ohosx64'),('ohos_arm64','grid-ohosarm64')]:
            leaf_url=consumer.PAGES+consumer.GROUP.replace('.','/')+'/'+module+'/'+VERSION+'/'+module+'-'+VERSION+'.module'
            root['variants'].append({'attributes':{'org.jetbrains.kotlin.native.target':target,'org.gradle.usage':'kotlin-api','org.gradle.category':'library'},'available-at':{'group':consumer.GROUP,'module':module,'version':VERSION,'url':leaf_url}})
            leaf={'component':{'group':consumer.GROUP,'module':'grid','version':VERSION,'url':self.root_url},'variants':[{'attributes':{'org.gradle.usage':'kotlin-api','org.jetbrains.kotlin.native.target':target,'org.gradle.category':'library'},'files':[artifact(module,leaf_url.removesuffix('.module')+'.klib',klib(target))]}]}
            self.responses[leaf_url]=json.dumps(leaf).encode()
        self.responses[self.root_url]=json.dumps(root).encode()

    def fetch(self,url,prefix):
        consumer.public_url(url,prefix);self.urls.append(url);data=self.responses[url]
        return data,{'url':url,'finalUrl':url,'status':200,'size':len(data),'sha256':consumer.digest(data),'authorizationSent':False,'cookieSent':False}

    def test_complete_root_routed_graph_and_payloads(self):
        with patch.object(consumer,'read_http',side_effect=self.fetch):result=consumer.fetch_graph(VERSION,self.output)
        self.assertEqual(len(self.urls),6)
        self.assertEqual(set(result['nativeArtifacts']),{'ohos_x64','ohos_arm64'})
        self.assertEqual(len(result['metadataPayload']),2)
        self.assertTrue(all(not item['authorizationSent'] for item in result['requests']))
        self.assertFalse(result['librarySourcesDownloaded'])

    def test_artifact_digest_mismatch_fails(self):
        data=json.loads(self.responses[self.root_url]);data['variants'][0]['files'][0]['sha256']='0'*64
        self.responses[self.root_url]=json.dumps(data).encode()
        with patch.object(consumer,'read_http',side_effect=self.fetch),self.assertRaisesRegex(RuntimeError,'size/SHA256 differs'):
            consumer.fetch_graph(VERSION,self.output)

    def test_wrong_leaf_owner_fails(self):
        url=next(url for url in self.responses if 'grid-ohosx64' in url and url.endswith('.module'))
        data=json.loads(self.responses[url]);data['component']['module']='other'
        self.responses[url]=json.dumps(data).encode()
        with patch.object(consumer,'read_http',side_effect=self.fetch),self.assertRaisesRegex(RuntimeError,'GMM owner differs'):
            consumer.fetch_graph(VERSION,self.output)

    def test_wrong_native_target_fails(self):
        url=next(url for url in self.responses if 'grid-ohosx64' in url and url.endswith('.module'))
        data=json.loads(self.responses[url]);declaration=data['variants'][0]['files'][0]
        jar_url=url.rsplit('/',1)[0]+'/'+declaration['url'];payload=klib('ohos_arm64')
        self.responses[jar_url]=payload;declaration.update(size=len(payload),sha256=consumer.digest(payload));self.responses[url]=json.dumps(data).encode()
        with patch.object(consumer,'read_http',side_effect=self.fetch),self.assertRaisesRegex(RuntimeError,'target or IR differs'):
            consumer.fetch_graph(VERSION,self.output)

    def test_anonymous_client_never_adds_auth_or_cookie(self):
        seen={}
        class Response:
            status=200;headers={'Content-Type':'application/json'}
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):return b'{}'
            def geturl(self):return consumer.PAGES+'test.module'
        class Opener:
            def open(self,request,timeout):seen['headers']=dict(request.header_items());return Response()
        with patch.object(consumer,'build_opener',return_value=Opener()) as factory:
            _,row=consumer.read_http(consumer.PAGES+'test.module',consumer.PAGES)
        self.assertEqual(factory.call_args.args[0].proxies,{})
        self.assertNotIn('Authorization',seen['headers']);self.assertNotIn('Cookie',seen['headers'])
        self.assertFalse(row['authorizationSent'])

    def test_incomplete_transport_retries_complete_response_only(self):
        attempts=[]
        class Response:
            status=200;headers={'Content-Type':'application/json','Content-Length':'2'}
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self):
                attempts.append(1)
                if len(attempts)<3:raise IncompleteRead(b'{',1)
                return b'{}'
            def geturl(self):return consumer.PAGES+'test.module'
        class Opener:
            def open(self,*args,**kwargs):return Response()
        with patch.object(consumer,'build_opener',return_value=Opener()),patch.object(consumer.time,'sleep') as sleep:
            data,row=consumer.read_http(consumer.PAGES+'test.module',consumer.PAGES)
        self.assertEqual(data,b'{}');self.assertEqual(row['requestAttempts'],3)
        self.assertEqual(len(row['transportFailures']),2);self.assertEqual(sleep.call_count,2)
        self.assertTrue(all(item['kind']=='TRANSPORT_INCOMPLETE_READ' for item in row['transportFailures']))

    def test_invalid_version_starts_no_http_or_process(self):
        env={'GRID_CONSUMER_OUTPUT':str(self.output),'GRID_VERSION':'$(untrusted)','GRID_SOURCE_SHA':SHA}
        with patch.dict(os.environ,env,clear=True),patch.object(consumer,'read_http') as fetch,patch.object(consumer.subprocess,'run') as run,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(consumer.main(),1)
        fetch.assert_not_called();run.assert_not_called()

    def test_child_environment_retains_loader_path_without_tokens(self):
        env={'GRID_CONSUMER_OUTPUT':str(self.output),'GRID_VERSION':VERSION,'GRID_SOURCE_SHA':SHA,'JAVA_HOME':'stub-jdk','PATH':'stub',
             'LD_LIBRARY_PATH':'stub-python-lib','ACTIONS_RUNTIME_TOKEN':'TEST_ONLY','GITHUB_TOKEN':'TEST_ONLY','GITCODE_TOKEN':'TEST_ONLY'}
        captured={}
        def run(argv,**kwargs):captured.update(kwargs['env']);return SimpleNamespace(returncode=23)
        with patch.dict(os.environ,env,clear=True),patch.object(consumer,'fetch_graph',return_value={}),patch.object(consumer,'fetch_tools',return_value=self.output),patch.object(consumer.subprocess,'run',side_effect=run),contextlib.redirect_stdout(io.StringIO()),contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(consumer.main(),1)
        self.assertEqual(captured['LD_LIBRARY_PATH'],'stub-python-lib')
        for name in ('ACTIONS_RUNTIME_TOKEN','GITHUB_TOKEN','GITCODE_TOKEN'):self.assertNotIn(name,captured)


if __name__=='__main__':unittest.main(verbosity=2)
