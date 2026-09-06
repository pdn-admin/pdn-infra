import json

with open('saved_results/pre_deploy_snapshot.json', 'r') as f:
    before = {u['email']: u for u in json.load(f)['users']}

# Latest export data (document 3 - post all deploys)
after_raw = {
    "shavit212@gmail.com": "E9", "hadas.antman@gmail.com": "T4", "whadas534@gmail.com": "A3",
    "efratdachner@gmail.com": "P6", "saradstudio@gmail.com": "E1", "mimran10@bezeqint.net": "A7",
    "yirat.gad@gmail.com": "E1", "nofiata@gmail.com": "E5", "dudlezak@gmail.com": "A3",
    "sshiralilo@gmail.com": "P6", "noam.shoshani@gmail.com": "P2", "sapird@gmail.com": "NA",
    "tgst.levi10@gmail.com": "T4", "alef.pey@gmail.com": "T8", "tamarronshapira@gmail.com": "A3",
    "st.shanni@gmail.com": "A3", "dannystryian@gmail.com": "A3", "teliakim@gmail.com": "P6",
    "ortalerez66@gmail.com": "P6", "netarimon9@gmail.com": "T8", "eran.wolfson@gmail.com": "T8",
    "imcluf@gmail.com": "A3", "adiglick@gmail.com": "T8", "tal.jakob@gmail.com": "E5",
    "hayimy.eng@gmail.com": "E9", "boni101@walla.com": "A7", "minasemoosh@gmail.com": "A3",
    "geyuka@gmail.com": "T8", "0rnamy53@gmail.com": "P6", "noamherzig@gmail.com": "P6",
    "yaelivinter@gmail.com": "P6", "gspitronot@gmail.com": "P6", "lioric.ta@gmail.com": "A7",
    "motieden52@gmail.com": "A3", "healthshelyat@gmail.com": "P6", "yaelhaime@gmail.com": "P6",
    "amit@israelnbeyond.com": "E9", "limor@apslaw.co.il": "E1", "shirit.design@gmail.com": "P6",
    "lilachad@gmail.com": "P6", "revitalhamer@gmail.com": "A3", "h.enati@gmail.com": "E5",
    "odemharris@gmail.com": "E5", "amirliora@gmail.com": "E1", "zilayh8@gmail.com": "A7",
    "kerennuni1809@gmail.com": "E9", "nogizahav@gmail.com": "A3", "keren.hadad@gmail.com": "P6",
    "happyness422@gmail.com": "P6", "inbalphotographer@gmail.com": "A3", "yehudit27@gmail.com": "P2",
    "moran.mbh@gmail.com": "P10", "micmic212@gmail.com": "E5", "inbarserfaty@gmail.com": "E9",
    "ronitmakom@gmail.com": "P6", "danahcpa@gmail.com": "A7", "inbal@inbalhealing.com": "E5",
    "ahuvazaafrani@gmail.com": "A3", "nd0547286681@gmail.com": "T12", "aviranmi@gmail.com": "A7",
    "ilanitrakut@gmail.com": "P10", "tomergur11@gmail.com": "NA", "ravivbarel1994@gmail.com": "P2",
    "reutsheffer73@gmail.com": "P6", "pdnnavigator@gmail.com": "A7", "wizdavid@gmail.com": "T8",
    "test@test.com": "E5", "aaa@aa.com": "NA", "tomergur+2222@gmail.com": "P10",
    "ofer2288440@gmail.com": "P2", "saramylove266@gmail.com": "P6", "tomergur@gmail.com": "P2",
    "yaelrapoport2@gmail.com": "A3", "izhar77@gmail.com": "P10", "tomergur+123@gmail.com": "P10",
    "einavmakover@gmail.com": "E9", "ronitamizur@gmail.com": "P10", "ysh0583217867@gmail.com": "A3",
    "st8768@gmail.com": "E5", "anna123benyehuda@gmail.com": "A3", "shimon@iamlegend.co.il": "E5",
    "shiry@solgar.co.il": "P6", "y0556623339@gmail.com": "P6", "64227e@gmail.com": "E1",
    "8414745@gmail.com": "P10", "canaandani@gmail.com": "E9", "am58lb@gmail.com": "T12",
    "pdncode100@gmail.com": "NA", "hadas.shefler@gmail.com": "E5", "youchy0@gmail.com": "E5",
    "yairmichl@gmail.com": "E9", "gotoalma@gmail.com": "A3", "miich2072@gmail.com": "T8",
    "tomergur1001@gmail.com": "E5", "office@hagitashur.co.il": "A7", "einatilani7@gmail.com": "P2",
    "tomergur101@gmail.com": "T8", "goren.anna2006@gmail.com": "T4", "pigimaya@gmail.com": "A7",
    "darpapir9893@gmail.com": "A3", "amnon.regev@gmail.com": "E9", "tomergur+A7@gmail.com": "A7",
    "rotem.tzuk@gmail.com": "E9", "kerens@bluewin.ch": "A7", "amitaitrip@gmail.com": "E1",
    "Daphna@ruthf.org": "A7", "tomergur+E1@gmail.com": "E1", "osnat.rabin@gmail.com": "P10",
    "s0548447640@gmail.com": "A3", "tomergur+T8@gmail.com": "T8", "tomergur+P2@gmail.com": "P2",
    "dansadeh21@gmail.com": "P2", "mesikalee@gmail.com": "A7", "mf8406@gmail.com": "P6",
    "tomergur+A11@gmail.com": "A11", "pdncode@gmail.com": "E1", "tomergur+P6@gmail.com": "P6",
    "tomergur+P10@gmail.com": "P10", "PdncodeA7@gmail.com": "NA", "tomergur+E5@gmail.com": "E5",
    "tomergur+E9@gmail.com": "E9", "tomergur+A3@gmail.com": "A3", "tomergur+T4@gmail.com": "T4",
    "tomergur+T12@gmail.com": "T12", "jacobi.gal@gmail.com": "E1", "info.dede.studio@gmail.com": "A7",
    "orna@84zebras.co.il": "A7", "naamuma@gmail.com": "NA", "israela.melech@gmail.com": "P2",
}

diffs = []
for email, new_code in after_raw.items():
    if email in before:
        old_code = before[email]['pdn_code']
        if old_code and old_code != new_code:
            diffs.append({
                'email': email,
                'name': before[email].get('name', ''),
                'before': old_code,
                'after': new_code
            })

print("BASELINE vs LATEST PRODUCTION (post all deploys)")
print("=" * 60)
print("Compared: %d users" % len(after_raw))
print("Differences: %d" % len(diffs))
print()
if diffs:
    for d in diffs:
        print("  %-20s | %4s -> %-4s | %s" % (d['name'], d['before'], d['after'], d['email']))
else:
    print("  ALL CODES MATCH BASELINE")
