Search.setIndex({docnames:["index","source/about","source/ambassador","source/arbiter","source/arbiter.verbatimdb","source/microengine","source/polyswarmclient"],envversion:{"sphinx.domains.c":1,"sphinx.domains.changeset":1,"sphinx.domains.cpp":1,"sphinx.domains.javascript":1,"sphinx.domains.math":1,"sphinx.domains.python":1,"sphinx.domains.rst":1,"sphinx.domains.std":1,sphinx:55},filenames:["index.rst","source/about.rst","source/ambassador.rst","source/arbiter.rst","source/arbiter.verbatimdb.rst","source/microengine.rst","source/polyswarmclient.rst"],objects:{"":{ambassador:[2,0,0,"-"],arbiter:[3,0,0,"-"],microengine:[5,0,0,"-"],polyswarmclient:[6,0,0,"-"]},"ambassador.eicar":{EicarAmbassador:[2,1,1,""]},"ambassador.eicar.EicarAmbassador":{next_bounty:[2,2,1,""]},"ambassador.filesystem":{FilesystemAmbassador:[2,1,1,""]},"ambassador.filesystem.FilesystemAmbassador":{next_bounty:[2,2,1,""]},"arbiter.verbatim":{VerbatimArbiter:[3,1,1,""]},"arbiter.verbatim.VerbatimArbiter":{scan:[3,2,1,""]},"microengine.clamav":{ClamavMicroengine:[5,1,1,""],ClamavScanner:[5,1,1,""]},"microengine.clamav.ClamavScanner":{scan:[5,2,1,""]},"microengine.eicar":{EicarMicroengine:[5,1,1,""]},"microengine.eicar.EicarMicroengine":{scan:[5,2,1,""]},"microengine.multi":{MultiMicroengine:[5,1,1,""]},"microengine.multi.MultiMicroengine":{scan:[5,2,1,""]},"microengine.scratch":{ScratchMicroengine:[5,1,1,""]},"microengine.yara":{YaraMicroengine:[5,1,1,""],YaraScanner:[5,1,1,""]},"microengine.yara.YaraScanner":{scan:[5,2,1,""]},"polyswarmclient.Client":{get_artifact:[6,2,1,""],get_artifacts:[6,2,1,""],list_artifacts:[6,2,1,""],listen_for_events:[6,2,1,""],make_request:[6,2,1,""],post_artifacts:[6,2,1,""],post_transactions:[6,2,1,""],run:[6,2,1,""],run_task:[6,2,1,""],schedule:[6,2,1,""],stop:[6,2,1,""],update_base_nonce:[6,2,1,""]},"polyswarmclient.ambassador":{Ambassador:[6,1,1,""]},"polyswarmclient.ambassador.Ambassador":{connect:[6,3,1,""],handle_run:[6,2,1,""],handle_settle_bounty:[6,2,1,""],next_bounty:[6,2,1,""],on_bounty_posted:[6,2,1,""],run:[6,2,1,""],run_task:[6,2,1,""]},"polyswarmclient.arbiter":{Arbiter:[6,1,1,""]},"polyswarmclient.arbiter.Arbiter":{connect:[6,3,1,""],handle_new_bounty:[6,2,1,""],handle_run:[6,2,1,""],handle_settle_bounty:[6,2,1,""],handle_vote_on_bounty:[6,2,1,""],run:[6,2,1,""],scan:[6,2,1,""]},"polyswarmclient.bloom":{BloomFilter:[6,1,1,""],chunk_to_bloom_bits:[6,5,1,""],get_bloom_bits:[6,5,1,""],get_chunks_for_bloom:[6,5,1,""]},"polyswarmclient.bloom.BloomFilter":{add:[6,2,1,""],extend:[6,2,1,""],from_iterable:[6,3,1,""],value:[6,4,1,""]},"polyswarmclient.bountiesclient":{BountiesClient:[6,1,1,""]},"polyswarmclient.bountiesclient.BountiesClient":{calculate_bloom:[6,2,1,""],get_assertion:[6,2,1,""],get_bounty:[6,2,1,""],get_parameters:[6,2,1,""],post_assertion:[6,2,1,""],post_bounty:[6,2,1,""],post_reveal:[6,2,1,""],post_vote:[6,2,1,""],settle_bounty:[6,2,1,""]},"polyswarmclient.events":{Callback:[6,1,1,""],Event:[6,1,1,""],OnInitializedChannelCallback:[6,1,1,""],OnNewAssertionCallback:[6,1,1,""],OnNewBlockCallback:[6,1,1,""],OnNewBountyCallback:[6,1,1,""],OnNewVerdictCallback:[6,1,1,""],OnQuorumReachedCallback:[6,1,1,""],OnRevealAssertionCallback:[6,1,1,""],OnRevealAssertionDueCallback:[6,1,1,""],OnRunCallback:[6,1,1,""],OnSettleBountyDueCallback:[6,1,1,""],OnSettledBountyCallback:[6,1,1,""],OnVoteOnBountyDueCallback:[6,1,1,""],RevealAssertion:[6,1,1,""],Schedule:[6,1,1,""],SettleBounty:[6,1,1,""],VoteOnBounty:[6,1,1,""]},"polyswarmclient.events.Callback":{register:[6,2,1,""],remove:[6,2,1,""],run:[6,2,1,""]},"polyswarmclient.events.OnInitializedChannelCallback":{run:[6,2,1,""]},"polyswarmclient.events.OnNewAssertionCallback":{run:[6,2,1,""]},"polyswarmclient.events.OnNewBlockCallback":{run:[6,2,1,""]},"polyswarmclient.events.OnNewBountyCallback":{run:[6,2,1,""]},"polyswarmclient.events.OnNewVerdictCallback":{run:[6,2,1,""]},"polyswarmclient.events.OnQuorumReachedCallback":{run:[6,2,1,""]},"polyswarmclient.events.OnRevealAssertionCallback":{run:[6,2,1,""]},"polyswarmclient.events.OnRevealAssertionDueCallback":{run:[6,2,1,""]},"polyswarmclient.events.OnRunCallback":{run:[6,2,1,""]},"polyswarmclient.events.OnSettleBountyDueCallback":{run:[6,2,1,""]},"polyswarmclient.events.OnSettledBountyCallback":{run:[6,2,1,""]},"polyswarmclient.events.OnVoteOnBountyDueCallback":{run:[6,2,1,""]},"polyswarmclient.events.Schedule":{empty:[6,2,1,""],get:[6,2,1,""],peek:[6,2,1,""],put:[6,2,1,""]},"polyswarmclient.microengine":{Microengine:[6,1,1,""]},"polyswarmclient.microengine.Microengine":{bid:[6,2,1,""],connect:[6,3,1,""],handle_new_bounty:[6,2,1,""],handle_reveal_assertion:[6,2,1,""],handle_settle_bounty:[6,2,1,""],run:[6,2,1,""],scan:[6,2,1,""]},"polyswarmclient.offersclient":{OffersClient:[6,1,1,""]},"polyswarmclient.reporter":{BountyProgress:[6,1,1,""],Reporter:[6,1,1,""],main:[6,5,1,""]},"polyswarmclient.reporter.BountyProgress":{all_complete:[6,2,1,""],check_block:[6,2,1,""],mark_stage_complete:[6,2,1,""]},"polyswarmclient.reporter.Reporter":{block_checker:[6,2,1,""],handle_assertion:[6,2,1,""],handle_run:[6,2,1,""],handle_settle_bounty:[6,2,1,""],run:[6,2,1,""],run_task:[6,2,1,""]},"polyswarmclient.scanner":{Scanner:[6,1,1,""]},"polyswarmclient.scanner.Scanner":{scan:[6,2,1,""]},"polyswarmclient.stakingclient":{StakingClient:[6,1,1,""]},"polyswarmclient.stakingclient.StakingClient":{get_parameters:[6,2,1,""],get_total_balance:[6,2,1,""],get_withdrawable_balance:[6,2,1,""],post_deposit:[6,2,1,""],post_withdraw:[6,2,1,""]},ambassador:{eicar:[2,0,0,"-"],filesystem:[2,0,0,"-"]},arbiter:{verbatim:[3,0,0,"-"],verbatimdb:[4,0,0,"-"]},microengine:{clamav:[5,0,0,"-"],eicar:[5,0,0,"-"],multi:[5,0,0,"-"],scratch:[5,0,0,"-"],yara:[5,0,0,"-"]},polyswarmclient:{Client:[6,1,1,""],ambassador:[6,0,0,"-"],arbiter:[6,0,0,"-"],bloom:[6,0,0,"-"],bountiesclient:[6,0,0,"-"],check_response:[6,5,1,""],events:[6,0,0,"-"],is_valid_ipfs_uri:[6,5,1,""],microengine:[6,0,0,"-"],offersclient:[6,0,0,"-"],reporter:[6,0,0,"-"],scanner:[6,0,0,"-"],stakingclient:[6,0,0,"-"]}},objnames:{"0":["py","module","Python module"],"1":["py","class","Python class"],"2":["py","method","Python method"],"3":["py","classmethod","Python class method"],"4":["py","attribute","Python attribute"],"5":["py","function","Python function"]},objtypes:{"0":"py:module","1":"py:class","2":"py:method","3":"py:classmethod","4":"py:attribute","5":"py:function"},terms:{"byte":[3,5,6],"case":6,"class":[2,3,5,6],"default":5,"int":[2,6],"new":6,"public":6,"return":[2,3,5,6],"true":6,The:6,about:[0,3,5,6],accept:6,account:6,add:6,addit:6,address:6,after:6,against:5,aggreg:5,all_complet:6,ambassador:0,amount:[2,6],analysi:[3,5,6],api_kei:6,arbit:0,arbiter_vote_window:6,arg:6,artifact:[2,3,5,6],artifact_uri:6,assert:[3,5,6],assertion_reveal_window:6,author:6,backend:5,balanc:6,base:[2,3,5,6],behavior:5,being:[2,3,5,6],benign:[2,6],bid:6,bit:[3,5,6],bitmask:6,block:[2,6],block_check:6,bloom:[],bloomfilt:6,bool:[3,5,6],bounti:[2,3,5,6],bountiescli:[],bounty_guid:6,bountyprogress:6,calcul:6,calculate_bloom:6,call:6,callback:6,chain:[2,3,5,6],channel:6,check:6,check_block:6,check_respons:6,chosen:5,chunk:6,chunk_to_bloom_bit:6,clamav:[],clamavmicroengin:5,clamavscann:5,clamd:5,classmethod:6,client:[2,3,5],commit:6,confidenti:6,connect:6,contain:6,content:0,contract:6,correl:6,custom:6,databas:3,deposit:6,detail:6,dict:6,differ:6,directori:2,durat:[2,6],each:6,eicar:[],eicarambassador:2,eicarmicroengin:5,either:2,els:6,emit:6,empti:6,enter:6,ethereum:6,even:1,event:[],execut:6,expect:6,expert:6,expir:6,extend:6,fals:6,file:[2,5,6],file_obj:6,filenam:6,filesystemambassador:2,filter:6,first:6,flexibl:6,from:[0,2,3,5,6],from_iter:6,gener:6,get:6,get_artifact:6,get_assert:6,get_bloom_bit:6,get_bounti:6,get_chunks_for_bloom:6,get_paramet:6,get_total_bal:6,get_withdrawable_bal:6,guid:[3,5,6],handle_assert:6,handle_new_bounti:6,handle_reveal_assert:6,handle_run:6,handle_settle_bounti:6,handle_vote_on_bounti:6,hash:[3,6],have:6,home:[2,3,5,6],http:6,implement:6,includ:[3,5,6],index:[0,6],indic:6,initi:6,insecure_transport:6,instanc:0,integ:6,interact:0,ipf:[2,6],ipfs_uri:[2,6],is_valid_ipfs_uri:6,iter:6,its:0,json:6,keyfil:6,known:3,kwarg:6,librari:0,list:6,list_artifact:6,listen:6,listen_for_ev:6,logic:6,loop:6,main:6,make:6,make_request:6,malici:[3,5,6],mark_stage_complet:6,mask:6,match:[3,5],metadata:[3,5,6],method:6,microengin:0,modul:0,msig:6,multi:6,multi_signatur:6,multimicroengin:5,multipl:5,name:6,nct:6,need:6,next_bounti:[2,6],nonc:6,none:[2,3,5,6],number:6,obj:6,object:6,offerscli:[],on_bounty_post:6,one:6,oninitializedchannelcallback:6,onnewassertioncallback:6,onnewblockcallback:6,onnewbountycallback:6,onnewverdictcallback:6,onquorumreachedcallback:6,onrevealassertioncallback:6,onrevealassertionduecallback:6,onruncallback:6,onsettlebountyduecallback:6,onsettledbountycallback:6,onvoteonbountyduecallback:6,open:6,oper:[5,6],option:[3,5,6],our:[3,5],overrid:6,packag:[],page:0,param:6,paramet:[2,3,5,6],pars:6,particular:6,password:6,path:6,payload:6,peek:6,place:[2,6],polyswarmcli:[2,3,5,6],polyswarmd:[0,6],polyswarmd_addr:6,polyswarmd_uri:6,portion:6,post:[2,6],post_artifact:6,post_assert:6,post_bounti:6,post_deposit:6,post_rev:6,post_transact:6,post_vot:6,post_withdraw:6,poster:6,put:6,python:0,queue:6,quorum:6,quorum_block:6,reach:6,receiv:6,regist:6,remov:6,report:[],repres:6,request:[2,6],respons:6,retriev:6,reveal:6,revealassert:6,root:6,rule:5,run:6,run_task:6,same:[3,5,6],sampl:[2,3,5],scan:[3,5,6],scanner:[3,5],schedul:6,scratch:[],scratchmicroengin:5,search:[0,5],secret:6,section:1,see:0,send:6,sent:[3,5],separ:6,set:6,settl:6,settle_bounti:6,settlebounti:6,settled_block:6,settler:6,side:6,sig:6,sign:6,simplifi:0,stake:6,stakingcli:[],statu:6,step:6,stop:6,str:[2,3,5,6],string:[2,5],sub:[5,6],submiss:[2,6],submit:[2,6],submodul:[2,5,6],success:6,support:6,termin:[2,6],test:[2,3,5,6],thi:[0,1,2,3,5,6],through:5,time:6,total:6,track:[3,5,6],track_nonc:6,transact:6,trigger:6,tupl:[2,3,5,6],tx_error_fat:6,type:[2,3,5,6],under:[3,5,6],unit:6,updat:6,update_base_nonc:6,upload:6,upon:6,uri:[2,6],use:[3,5,6],used:6,valid:6,valid_bloom:6,valu:6,value_hash:6,variou:0,verbatimarbit:3,verbatimdb:3,verdict:[3,5,6],via:6,vote:6,voteonbounti:6,voter:6,want:1,websocket:6,when:6,whether:[3,5,6],which:[2,3,5,6],wip:0,withdraw:6,within:6,yara:[],yaramicroengin:5,yarascann:5},titles:["Welcome to polyswarm-client\u2019s documentation!","Here\u2019s a Thing!","Ambassador Package","Arbiter Package","Arbiter Verbatimdb Package","Microengine Package","Polywarm Client Package"],titleterms:{"new":[],Adding:[],ambassador:[2,6],arbit:[3,4,6],bloom:6,bountiescli:6,clamav:5,client:[0,6],content:[2,3,4,5,6],document:0,eicar:[2,5],event:6,filesystem:2,header:[],here:1,indic:0,microengin:[5,6],modul:[2,3,4,5,6],multi:5,offerscli:6,packag:[2,3,4,5,6],polyswarm:0,polyswarmcli:[],polywarm:6,polywarmcli:[],report:6,scanner:6,scratch:5,stakingcli:6,submodul:3,subpackag:[],tabl:0,thing:1,verbatim:3,verbatimdb:4,welcom:0,what:0,yara:5}})